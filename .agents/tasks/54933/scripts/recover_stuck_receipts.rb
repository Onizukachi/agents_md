# Зависшие чеки Uniteller (LT-54933).
# Касса пробила чек, а ответ к нам не дошёл за 30 секунд, и повторы получают «Order cannot be paid».
# Скрипт берёт пробитый чек из results Uniteller и сохраняет его так же, как FiscalRouter
# после успешного ответа кассы. Чек записывается, только если в Uniteller ровно один подходящий:
# того же типа (приход/возврат), на ту же сумму и ещё не записанный в другой наш чек заказа.
#
# Вставить весь файл в прод-консоль. Внизу, в блоке «Запуск»:
#   1. explain(explain_ids)           — только чтение: что Uniteller хранит по 9 чекам, которые не нашлись
#   2. recover(found_ids, apply: true) — запись 58 найденных чеков, письма клиентам — по SEND_EMAILS
#   3. stale_retries(found_ids).size  — сколько ретраев RoutersWorker осталось по записанным чекам;
#      удалить их — строка ниже, сейчас закомментирована
#
# Другие вызовы: stuck_ids — все зависшие чеки, recover(ids) — пробный прогон без записи.

SEND_EMAILS = false # письма клиентам с чеками, как при обычной фискализации; false — без писем

# Непрофискализированные чеки примерно с 13.10, которые уже отправлялись в кассу
def stuck_ids(from_id = 610_000)
  sent = ReceiptLog.where('receipt_id >= ?', from_id).select(:receipt_id)
  Receipt.where('id >= ?', from_id).where(parsed_data: nil, fiscalization_skipped: false, id: sent).order(:id).pluck(:id)
end

def receipt_processor(receipt)
  fiscalizer = receipt.fiscalizer || FiscalRouter.fiscalizer_for(receipt)
  [fiscalizer, fiscalizer.klass.new(receipt.id, receipt.operation_type, fiscalizer)]
end

# Заказ из results Uniteller и все чеки, которые касса пробила по этому OrderID
def uniteller_order(processor, order_id)
  response = ExternalRequest.new(
    "#{processor.config[:base_url]}results",
    method: :post,
    body: processor.receipt_info_params.merge(ShopOrderNumber: order_id)
  ).run
  raise "results: HTTP #{response.code} #{response.return_message}" unless response.success?

  order = Nokogiri::XML(response.body).css('order').find { |node| node.at_css('ordernumber')&.text == order_id }
  encoded = order&.at_css('receipt')&.text
  [order, encoded.present? ? Array(JSON.parse(Base64.decode64(encoded))) : []]
end

def recover_receipt(receipt, apply:, send_emails:)
  return { result: 'уже профискализирован' } if receipt.fiscalized?
  return { result: 'фискализация запрещена (субагент, skip_fiscalization или тестовая карта)' } if receipt.fiscalization_forbidden?

  fiscalizer, processor = receipt_processor(receipt)
  return { result: "касса #{fiscalizer.name}, пропускаем" } unless fiscalizer.name == 'Uniteller'

  order_id = processor.send(:external_order_id)
  type = receipt.purchase? ? 0 : 1
  total = processor.receipt_params[:total].to_s.to_d
  taken = receipt.order.fetch_all_receipts.where.not(id: receipt.id).filter_map { |other| other.raw_data&.dig('fiscal', 'id') }
  found = uniteller_order(processor, order_id).last.select do |data|
    data.dig('fiscal', 'type').to_i == type && data['total'].to_s.to_d == total && taken.exclude?(data.dig('fiscal', 'id'))
  end
  return { order_id: order_id, result: "подходящих чеков в Uniteller #{found.size}" } unless found.one?

  data = found.first
  info = { order_id: order_id, fiscal_id: data.dig('fiscal', 'id'), fiscal_date: data.dig('fiscal', 'date'), total: data['total'] }
  return info.merge(result: 'найден') unless apply

  Receipt.transaction do
    processor.send(:process_success_response, order_idp: receipt.fiscal_number)
    Callbacks::Receipt.call(receipt, fiscalizer: fiscalizer.name, raw_data: data) || raise('чек не записался')
  end

  # Как в FiscalRouter: группа набрала все чеки — уходит письмо клиенту. Без письма — мимо колбэка
  group = receipt.receipt_wait_group
  if send_emails
    group.update!(fiscalized_total: group.fiscalized_total + 1)
  else
    group.update_column(:fiscalized_total, group.fiscalized_total + 1)
  end
  info.merge(result: 'записан')
end

def recover(ids, apply: false, send_emails: SEND_EMAILS)
  ids.each do |id|
    row = { id: id }
    receipt = Receipt.find(id)
    row.merge!(order: receipt.order&.id, kind: "#{receipt.receipt_type}/#{receipt.operation_type}")
    row.merge!(recover_receipt(receipt, apply: apply, send_emails: send_emails))
  rescue StandardError => e
    row[:result] = "ошибка #{e.class}: #{e.message.to_s.first(200)}"
  ensure
    pp row
  end
  nil
end

# Что Uniteller хранит по чекам, которые не нашлись: статус и сумма заказа и все его чеки рядом с тем, что ждём мы
def explain(ids)
  ids.each do |id|
    row = { id: id }
    receipt = Receipt.find(id)
    _fiscalizer, processor = receipt_processor(receipt)
    row[:order_id] = processor.send(:external_order_id)
    row[:expected] = "#{receipt.purchase? ? 'приход' : 'возврат'} #{processor.receipt_params[:total]}"
    order, receipts = uniteller_order(processor, row[:order_id])
    row[:uniteller] = order ? { status: order.at_css('status')&.text, total: order.at_css('total')&.text } : 'заказа нет'
    row[:receipts] = receipts.map do |data|
      {
        type: data.dig('fiscal', 'type').to_i == 1 ? 'возврат' : 'приход',
        total: data['total'],
        fiscal_id: data.dig('fiscal', 'id'),
        fiscal_date: data.dig('fiscal', 'date'),
      }
    end
  rescue StandardError => e
    row[:result] = "ошибка #{e.class}: #{e.message.to_s.first(200)}"
  ensure
    pp row
  end
  nil
end

# Ретраи RoutersWorker по уже профискализированным чекам: данных не меняют, только снова падают в Sentry
def stale_retries(ids)
  fiscalized = Receipt.where(id: ids).select(&:fiscalized?).map(&:id)
  Sidekiq::RetrySet.new.select do |job|
    job.klass == 'RoutersWorker' && fiscalized.include?(job.args.first.to_h['receipt_id'])
  end
end

# ===== Запуск =====

# 58 чеков, которые пробный прогон 19.10 нашёл однозначно
found_ids = [
  610415, 611096, 611097, 611100, 611102, 611103, 611104, 611106, 611107, 611108, 611109, 611110,
  611111, 611112, 611113, 611114, 611120, 611121, 611129, 611326, 612931, 614678, 614730, 614733,
  614736, 614737, 614747, 614783, 614790, 614820, 614829, 614840, 614857, 614874, 614888, 614914,
  614927, 614936, 614937, 614940, 614941, 614942, 614948, 614953, 615077, 615155, 615180, 615201,
  615205, 615206, 615230, 615272, 615277, 615301, 615363, 615383, 615389, 615506
]

# 9 чеков из сбоя 14.10 11:30–12:47 МСК: заказ в Uniteller оплачен, а подходящего чека нет
explain_ids = [611098, 611099, 611101, 611105, 611115, 611118, 611123, 611124, 611128]

explain(explain_ids)
recover(found_ids, apply: true)
pp stale_retries(found_ids).size
# stale_retries(found_ids).each(&:delete)
