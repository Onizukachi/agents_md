# Детализации старого флоу по заказам, полностью оплаченным сертификатом дороже заказа (LT-54933).
# Строки детализации сохранены на номинал сертификата, а оплата сертификатом в чеке — на цену заказа,
# поэтому Uniteller отклоняет чек: «Field Receipt has invalid payments 3». Скрипт уменьшает строку тура
# на остаток сертификата (номинал − цена заказа) и отправляет этот же чек в кассу заново.
# OrderID, логи и история чека не меняются: Uniteller этот OrderID не оплачивал, чек отклонялся сразу.
#
# Шаги в прод-консоли:
#   1. Вставить весь файл.
#   2. ids = certificate_detailing_ids; pp ids          — какие детализации подходят (ожидаем 13)
#   3. fix_certificate_detailings(ids)                  — пробный прогон, ничего не пишет; вывод прислать
#   4. fix_certificate_detailings(ids, apply: true)     — исправить строку тура и профискализировать;
#                                                         после успешного чека клиенту уйдёт письмо
#      fix_certificate_detailings(ids, apply: true, send_emails: false) — то же без письма клиенту
#
# Блок «Запуск» внизу сразу исправляет и фискализирует 17 детализаций без писем клиентам.
#
# Найденные 20.10 детализации: 560346, 560568, 562808, 562811, 565398, 589663, 591618, 595492, 599694,
# 602465, 605899, 605917, 607429.

# Непрофискализированные детализации старого флоу, у которых строки на номинал сертификата дороже заказа
def certificate_detailing_ids(from_id = 500_000)
  Receipt.where('receipts.id >= ?', from_id)
    .where(object_type: 'Order', receipt_type: 'detailed', operation_type: 'purchase', is_technical: false,
           parsed_data: nil, fiscalization_skipped: false)
    .joins('JOIN orders ON orders.id = receipts.object_id JOIN coupons ON coupons.id = orders.coupon_id')
    .where.not(coupons: { certificate_id: nil })
    .order(:id).select { |receipt| oversized_certificate?(receipt) }.map(&:id)
end

def oversized_certificate?(receipt)
  order = receipt.order
  !Receipts::AgentFlow.enabled?(order) &&
    order.certificate_applied? &&
    order.discount_fully_cover?(:certificate) &&
    order.certificate_amount > order.full_price &&
    receipt.line_items_v2.sum(:price) == order.certificate_amount
end

def receipt_totals(receipt)
  fiscalizer = receipt.fiscalizer || FiscalRouter.fiscalizer_for(receipt)
  params = fiscalizer.klass.new(receipt.id, receipt.operation_type, fiscalizer).receipt_params
  lines = params[:lines].sum { |line| line.to_h.stringify_keys['sum'].to_s.to_d }
  [lines, params[:total].to_s.to_d]
end

# Как FiscalRouter, но счётчик группы чеков обновляется мимо колбэка, который отправляет письмо клиенту
def fiscalize_without_email(receipt)
  fiscalizer = receipt.fiscalizer || FiscalRouter.fiscalizer_for(receipt)
  processor = fiscalizer.klass.new(receipt.id, receipt.operation_type, fiscalizer)
  processor.process_iacheck if fiscalizer.has_preauth?
  response = processor.process_capture_fiscalization
  raise "no receipt in the response: #{response.inspect.first(200)}" if response.blank? || response[:receipt].blank?

  Callbacks::Receipt.call(receipt, fiscalizer: fiscalizer.name, raw_data: response[:receipt]) || raise('receipt was not saved')
  group = receipt.receipt_wait_group
  group.update_column(:fiscalized_total, group.fiscalized_total + 1)
end

def fix_certificate_detailing(receipt, apply:, send_emails:)
  return { result: 'already fiscalized' } if receipt.fiscalized?
  return { result: 'does not match: not an oversized certificate detailing' } unless oversized_certificate?(receipt)

  order = receipt.order
  excess = order.certificate_amount - order.full_price
  tours = receipt.line_items_v2.where(item_type: Order.name).where.not(title: LineItemV2::LICENCE_NAME).to_a
  return { result: "tour lines: #{tours.size}" } unless tours.one?

  tour = tours.first
  return { result: "tour line #{tour.price} is not bigger than the excess #{excess}" } unless tour.price > excess

  lines_now, payments_total = receipt_totals(receipt)
  info = {
    certificate: order.certificate_amount.to_i,
    order_price: order.full_price.to_i,
    tour_before: tour.price.to_i,
    tour_after: (tour.price - excess).to_i,
    lines_now: lines_now.to_i,
    lines_after: (lines_now - excess).to_i,
    payments: payments_total.to_i,
  }
  return info.merge(result: 'lines after fix do not match payments, skipped') unless lines_now - excess == payments_total
  return info.merge(result: 'matches, not fixed') unless apply

  Receipt.transaction do
    tour.update!(price: tour.price - excess)
    lines, total = receipt_totals(receipt.reload)
    raise "after fix lines #{lines} != payments #{total}" unless lines == total
  end

  send_emails ? FiscalRouter.process(receipt.id) : fiscalize_without_email(receipt.reload)
  receipt.reload
  info.merge(fiscal_id: receipt.raw_data&.dig('fiscal', 'id'), result: receipt.fiscalized? ? 'fixed and fiscalized' : 'fixed, not fiscalized')
end

def fix_certificate_detailings(ids, apply: false, send_emails: true)
  ids.each do |id|
    row = { id: id }
    receipt = Receipt.find(id)
    row.merge!(order: receipt.object_id, order_id: "#{receipt.fiscal_number}-d")
    row.merge!(fix_certificate_detailing(receipt, apply: apply, send_emails: send_emails))
  rescue StandardError => e
    row[:result] = "error #{e.class}: #{e.message.to_s.first(200)}"
  ensure
    pp row
  end
  nil
end

# ===== Запуск =====

# 17 детализаций, у которых пробный прогон 20.10 показал «matches, not fixed»
# (без пяти на отменённых заказах: 534556, 560346, 560568, 605899, 605917)
fix_ids = [
  514028, 517174, 524028, 543259, 544641, 546217, 556179, 558104, 562808,
  562811, 565398, 589663, 591618, 595492, 599694, 602465, 607429
]

fix_certificate_detailings(fix_ids, apply: true, send_emails: false)
