# Старые зависшие чеки Uniteller (LT-54933): непрофискализированные чеки, на повтор которых Uniteller отвечал
# «уже проведено» (iapay Result 21, cancel Code 03/04/05). Ретраи по ним давно закончились, поэтому правка
# в FiscalRouter их не подхватит. Большая часть — детализации 11.10, созданные заново после отката базы 10.10:
# первая отправка прошла в откатившемся окне, и Uniteller хранит пробитый чек.
#
# Скрипт берёт пробитый чек из results и сохраняет его так же, как FiscalRouter после успешного ответа кассы.
# Записывает, только если в Uniteller ровно один подходящий чек: того же типа, на ту же сумму и с фискальным id,
# не записанным в другой наш чек заказа. Чеки партнёров с запретом фискализации пропускаются.
#
# Шаги в прод-консоли:
#   1. Вставить весь файл. Внизу сразу запустится пробный прогон: он ничего не пишет, печатает итог по группам
#      и списки id. Вывод прислать.
#   2. После разбора: recover_old(found_ids, apply: true, send_emails: false)
#      found_ids — список из итога пробного прогона (ключ "found").

def already_processed_ids(from_id = 400_000)
  signals = ['%<Result>21</Result>%', '%"Code":"03"%', '%"Code":"04"%', '%"Code":"05"%']
  condition = signals.map { "JSON_UNQUOTE(JSON_EXTRACT(response, '$.response')) LIKE ?" }.join(' OR ')
  logs = ReceiptLog.where('receipt_id >= ?', from_id).where(condition, *signals)
  Receipt.where(id: logs.select(:receipt_id)).where(parsed_data: nil, fiscalization_skipped: false).order(:id).pluck(:id)
end

def old_uniteller_receipts(processor, order_id)
  response = ExternalRequest.new(
    "#{processor.config[:base_url]}results",
    method: :post,
    body: processor.receipt_info_params.merge(ShopOrderNumber: order_id)
  ).run
  raise "results: HTTP #{response.code} #{response.return_message}" unless response.success?

  order = Nokogiri::XML(response.body).css('order').find { |node| node.at_css('ordernumber')&.text == order_id }
  return [nil, []] unless order

  encoded = order.at_css('receipt')&.text
  [order.at_css('status')&.text, encoded.present? ? Array(JSON.parse(Base64.decode64(encoded))) : []]
end

def old_lines(lines)
  Array(lines).map do |line|
    line = line.to_h.stringify_keys
    [line['name'].to_s.squish.first(128), line['sum'].to_s.to_d]
  end.sort
end

def recover_old_receipt(receipt, apply:, send_emails:)
  return { result: 'already_fiscalized' } if receipt.fiscalized?
  return { result: 'fiscalization_forbidden' } if receipt.fiscalization_forbidden?

  fiscalizer = receipt.fiscalizer || FiscalRouter.fiscalizer_for(receipt)
  return { result: 'not_uniteller' } unless fiscalizer.name == 'Uniteller'

  processor = fiscalizer.klass.new(receipt.id, receipt.operation_type, fiscalizer)
  order_id = processor.send(:external_order_id)
  status, receipts = old_uniteller_receipts(processor, order_id)
  return { order_id: order_id, result: 'no_order_in_uniteller' } if status.nil?
  return { order_id: order_id, status: status, result: 'no_receipts_in_uniteller' } if receipts.empty?

  expected = processor.receipt_params
  type = receipt.purchase? ? 0 : 1
  taken = receipt.order.fetch_all_receipts.where.not(id: receipt.id).filter_map { |other| other.raw_data&.dig('fiscal', 'id') }
  found = receipts.select do |data|
    data.is_a?(Hash) && data.dig('fiscal', 'type').to_i == type &&
      data['total'].to_s.to_d == expected[:total].to_s.to_d && taken.exclude?(data.dig('fiscal', 'id'))
  end
  unless found.one?
    return { order_id: order_id, status: status, candidates: found.size, in_uniteller: receipts.size,
             result: found.empty? ? 'no_matching_receipt' : 'ambiguous' }
  end

  data = found.first
  info = { order_id: order_id, fiscal_id: data.dig('fiscal', 'id'), fiscal_date: data.dig('fiscal', 'date'),
           total: data['total'], lines_match: old_lines(data['lines']) == old_lines(expected[:lines]) }
  return info.merge(result: 'found') unless apply

  Receipt.transaction do
    processor.send(:process_success_response, order_idp: receipt.fiscal_number)
    Callbacks::Receipt.call(receipt, fiscalizer: fiscalizer.name, raw_data: data) || raise('receipt was not saved')
  end
  group = receipt.receipt_wait_group
  if send_emails
    group.update!(fiscalized_total: group.fiscalized_total + 1)
  else
    group.update_column(:fiscalized_total, group.fiscalized_total + 1)
  end
  info.merge(result: 'recovered')
end

def recover_old(ids, apply: false, send_emails: false)
  rows = ids.map do |id|
    row = { id: id }
    receipt = Receipt.find(id)
    row.merge!(kind: "#{receipt.receipt_type}/#{receipt.operation_type}", created: receipt.created_at.to_date.to_s)
    row.merge!(recover_old_receipt(receipt, apply: apply, send_emails: send_emails))
  rescue StandardError => e
    row.merge(result: 'error', error: "#{e.class}: #{e.message.to_s.first(150)}")
  end

  groups = rows.group_by { |row| row[:result] }
  pp(groups.transform_values(&:size))
  pp(lines_mismatch: rows.select { |row| row[:lines_match] == false }.map { |row| row[:id] })
  groups.each do |result, group_rows|
    pp(result => group_rows.map { |row| row[:id] })
  end
  groups.except('found', 'recovered', 'already_fiscalized').each do |result, group_rows|
    group_rows.first(5).each { |row| pp(row) }
  end
  nil
end

# ===== Запуск: пробный прогон, ничего не пишет =====

old_ids = already_processed_ids
pp old_ids.size
recover_old(old_ids)
