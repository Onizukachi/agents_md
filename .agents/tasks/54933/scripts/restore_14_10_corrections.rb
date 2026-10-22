# 9 чеков из сбоя Uniteller 14.10 (LT-54933). Uniteller пробил их 22.10 чеками коррекции прихода:
# fiscal.type = 2, в данных correctionType/causeDocumentDate/correctionSubject, в qr n=1 (приход).
# Сумма, строки и оплаты совпадают с нашими. Хотфикс ждёт тип 0 и такие чеки не берёт, поэтому здесь
# та же проверка, что ReceiptInfo#same_as_sent?, только тип — коррекция прихода. Записывает чек как
# успешный ответ кассы, без писем клиентам.
#
# 1. Вставить файл: внизу пробный прогон, он ничего не пишет.
# 2. Запись: restore_corrections(IDS, apply: true)

IDS = [611098, 611099, 611101, 611105, 611115, 611118, 611123, 611124, 611128].freeze
CORRECTION_PURCHASE_TYPE = 2

def correction_receipts(receipt, processor)
  order_id = processor.send(:external_order_id)
  order = processor.external_status[:orders].find { |item| item[:fields]['ordernumber'] == order_id }
  expected = processor.receipt_params
  taken = receipt.order.fetch_all_receipts.where.not(id: receipt.id).filter_map { |other| other.raw_data&.dig('fiscal', 'id') }

  found = Array(order&.dig(:receipt)).select do |data|
    data.is_a?(Hash) &&
      data.dig('fiscal', 'type').to_i == CORRECTION_PURCHASE_TYPE &&
      data.dig('fiscal', 'register', 'qr').to_s.match?(/(\A|&)n=1(&|\z)/) &&
      data['total'].to_s.to_d == expected[:total].to_s.to_d &&
      processor.send(:sent_lines, data['lines']) == processor.send(:sent_lines, expected[:lines]) &&
      processor.send(:sent_payments, data['payments']) == processor.send(:sent_payments, expected[:payments]) &&
      taken.exclude?(data.dig('fiscal', 'id'))
  end
  [order_id, found]
end

def restore_correction(receipt, apply:)
  return { result: 'already_fiscalized' } if receipt.fiscalized?
  return { result: 'fiscalization_forbidden' } if receipt.fiscalization_forbidden?
  return { result: 'not_purchase' } unless receipt.purchase?

  fiscalizer = receipt.fiscalizer || FiscalRouter.fiscalizer_for(receipt)
  return { result: 'not_uniteller' } unless fiscalizer.name == 'Uniteller'

  processor = fiscalizer.klass.new(receipt.id, receipt.operation_type, fiscalizer)
  order_id, found = correction_receipts(receipt, processor)
  return { order_id: order_id, candidates: found.size, result: 'no_single_match' } unless found.one?

  data = found.first
  row = {
    order_id: order_id,
    fiscal_id: data.dig('fiscal', 'id'),
    fiscal_date: data.dig('fiscal', 'date'),
    correction: data.slice('correctionType', 'causeDocumentDate', 'correctionSubject'),
  }
  return row.merge(result: 'found') unless apply

  # Как FiscalRouter после успешного ответа, но счётчик группы мимо колбэка, чтобы не ушло письмо
  Receipt.transaction do
    processor.send(:process_success_response, order_idp: receipt.fiscal_number)
    Callbacks::Receipt.call(receipt, fiscalizer: fiscalizer.name, raw_data: data) || raise('receipt was not saved')
  end
  group = receipt.receipt_wait_group
  group.update_column(:fiscalized_total, group.fiscalized_total + 1)
  row.merge(result: 'recovered', fiscalized: receipt.reload.fiscalized?)
end

def restore_corrections(ids, apply: false)
  ids.each do |id|
    row = { id: id }
    receipt = Receipt.find(id)
    row.merge!(kind: "#{receipt.receipt_type}/#{receipt.operation_type}")
    row.merge!(restore_correction(receipt, apply: apply))
  rescue StandardError => e
    row.merge!(result: 'error', error: "#{e.class}: #{e.message.to_s.first(150)}")
  ensure
    pp row
  end
  nil
end

# ===== Пробный прогон, ничего не пишет =====
restore_corrections(IDS)
