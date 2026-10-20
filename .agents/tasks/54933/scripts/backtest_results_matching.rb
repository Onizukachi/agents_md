# Сверка задним числом (LT-54933): насколько точно поиск в results Uniteller находит наш чек.
# Берём уже профискализированные чеки Uniteller разных типов и делаем вид, что ответ кассы потерян:
# ищем чек в results и сравниваем найденный фискальный id с тем, что лежит у нас в raw_data.
# Только чтение: в базу ничего не пишется, в Uniteller уходят только запросы results.
#
# Вставить весь файл в прод-консоль. Внизу запуск:
#   backtest(backtest_sample) — строка на каждый чек, где что-то не так, и итог по типам чеков
#
# Две сверки:
#   simple — тип чека (приход/возврат), сумма, фискальный id не занят другим нашим чеком заказа
#            (так работал скрипт восстановления 19.10)
#   strict — simple плюс строки (название и сумма) и блок оплат (kind, type, сумма)
#
# Итог по каждой сверке: ok — нашёлся ровно наш чек; wrong — нашёлся чужой чек; ambiguous — подходит
# несколько; not_found — ни одного. Опасен только wrong: с ним восстановление записало бы чужой чек.

BACKTEST_FROM_ID = 580_000 # чеки примерно с начала сентября
BACKTEST_PER_KIND = 40

BACKTEST_KINDS = {
  'advance' => { receipt_type: 'advanced', operation_type: 'purchase', is_technical: false },
  'advance_refund' => { receipt_type: 'advanced', operation_type: 'refund', is_technical: false },
  'transfer_purchase' => { receipt_type: 'advanced', operation_type: 'purchase', is_technical: true },
  'transfer_refund' => { receipt_type: 'advanced', operation_type: 'refund', is_technical: true },
  'detailing' => { receipt_type: 'detailed', operation_type: 'purchase', is_technical: false },
  'detailed_refund' => { receipt_type: 'detailed', operation_type: 'refund', is_technical: false },
  'storno' => { receipt_type: 'detailed', operation_type: 'refund', is_technical: true },
}.freeze

# Последние профискализированные чеки Uniteller каждого типа
def backtest_sample(from_id: BACKTEST_FROM_ID, per_kind: BACKTEST_PER_KIND)
  uniteller = Fiscalizer.find_by!(name: 'Uniteller')
  BACKTEST_KINDS.values.flat_map do |conditions|
    Receipt.where('id >= ?', from_id).where(conditions).where(fiscalizer_id: uniteller.id).where.not(parsed_data: nil)
      .order(id: :desc).limit(per_kind).pluck(:id)
  end
end

def backtest_kind(receipt)
  BACKTEST_KINDS.find do |_kind, conditions|
    conditions.all? { |attribute, value| receipt.public_send(attribute) == value }
  end&.first
end

def backtest_lines(lines)
  Array(lines).map do |line|
    line = line.to_h.stringify_keys
    [line['name'].to_s.squish.first(128), line['sum'].to_s.to_d]
  end.sort
end

def backtest_payments(payments)
  Array(payments).map do |payment|
    payment = payment.to_h.stringify_keys
    [payment['kind'].to_i, payment['type'].to_i, payment['amount'].to_s.to_d]
  end.sort
end

# Все чеки Uniteller по OrderID; один запрос на OrderID за прогон
def backtest_results(processor, order_id)
  @backtest_cache ||= {}
  @backtest_cache[[processor.receipt.organization_id, order_id]] ||= begin
    response = ExternalRequest.new(
      "#{processor.config[:base_url]}results",
      method: :post,
      body: processor.receipt_info_params.merge(ShopOrderNumber: order_id)
    ).run
    raise "results: HTTP #{response.code} #{response.return_message}" unless response.success?

    order = Nokogiri::XML(response.body).css('order').find { |node| node.at_css('ordernumber')&.text == order_id }
    encoded = order&.at_css('receipt')&.text
    encoded.present? ? Array(JSON.parse(Base64.decode64(encoded))) : []
  end
end

def backtest_verdict(candidates, actual)
  return :not_found if candidates.empty?
  return :ambiguous unless candidates.one?

  candidates.first.dig('fiscal', 'id') == actual ? :ok : :wrong
end

def backtest(ids)
  summary = Hash.new { |hash, kind| hash[kind] = Hash.new(0) }

  ids.each do |id|
    kind = nil
    receipt = Receipt.find(id)
    kind = backtest_kind(receipt) || 'other'
    fiscalizer = receipt.fiscalizer
    processor = fiscalizer.klass.new(receipt.id, receipt.operation_type, fiscalizer)
    order_id = processor.send(:external_order_id)
    expected = processor.receipt_params
    actual = receipt.raw_data&.dig('fiscal', 'id')
    type = receipt.purchase? ? 0 : 1
    taken = receipt.order.fetch_all_receipts.where.not(id: receipt.id).filter_map { |other| other.raw_data&.dig('fiscal', 'id') }
    uniteller = backtest_results(processor, order_id)

    simple = uniteller.select do |data|
      data.dig('fiscal', 'type').to_i == type &&
        data['total'].to_s.to_d == expected[:total].to_s.to_d &&
        taken.exclude?(data.dig('fiscal', 'id'))
    end
    strict = simple.select do |data|
      backtest_lines(data['lines']) == backtest_lines(expected[:lines]) &&
        backtest_payments(data['payments']) == backtest_payments(expected[:payments])
    end

    simple_verdict = backtest_verdict(simple, actual)
    strict_verdict = backtest_verdict(strict, actual)
    summary[kind][:total] += 1
    summary[kind]["simple_#{simple_verdict}"] += 1
    summary[kind]["strict_#{strict_verdict}"] += 1
    next if simple_verdict == :ok && strict_verdict == :ok

    pp(
      id: id,
      kind: kind,
      order_id: order_id,
      actual: actual,
      expected_total: expected[:total],
      simple: simple_verdict,
      strict: strict_verdict,
      in_uniteller: uniteller.map { |data| "type #{data.dig('fiscal', 'type')}, total #{data['total']}, #{data.dig('fiscal', 'id')}" }
    )
  rescue StandardError => e
    summary[kind || 'not_loaded'][:error] += 1
    pp(id: id, kind: kind, error: "#{e.class}: #{e.message.to_s.first(200)}")
  end

  pp summary.transform_values(&:to_h)
  nil
end

# ===== Запуск =====

sample_ids = backtest_sample
pp sample_ids.size
backtest(sample_ids)
