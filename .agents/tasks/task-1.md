# Задача: вынести Uniteller 3DS из iframe в отдельную вкладку

## 1. Бизнес контекст для задачи

- Сейчас карточная 3DS-проверка для Uniteller исторически завязана на iframe-flow.
- Цель: отказаться от iframe на фронте и открывать ACS-форму банка в отдельной вкладке.
- После ввода OTP клиент должен возвращаться на наш backend `redirect_3ds`, а затем попадать на отдельную страницу `acs_result`, где frontend сам дочитает `PaRes/cres` из `window` и вызовет backend `pay_3ds`.
- Нужно отдельно сохранить и не потерять альтернативный вариант, где frontend-запрос `pay_3ds` вообще не нужен, а backend сам вызывает `make_pay` внутри `redirect_3ds`.

## 2. Ключевые решения и обоснования

- `TermUrl` у Uniteller/ACS работает как URL возврата внутри текущего контекста challenge.
- В старом iframe-flow `redirect_3ds` был технической страницей: он выставлял `window.LT_Payment3dsData`, а внешний фронт читал эти данные из `iframe.contentWindow`.
- Для separate-tab flow промежуточный `POST /payment/acs_result` через auto-submit форму не является конечным решением:
  - он был удобен как прокладка для iframe,
  - но в отдельной вкладке frontend не должен зависеть от внешнего родителя.
- Целевой flow для separate-tab:
  1. ACS возвращает пользователя на `POST /payment/redirect_3ds/:payment_id`
  2. `redirect_3ds` сохраняет `PaRes/cres` в `payment.data_3ds`
  3. затем backend делает redirect на отдельную страницу `GET /payment/acs_result/:payment_id`
  4. `acs_result` рендерит frontend entrypoint и/или кладет `PaRes/cres` в `window`
  5. frontend на странице `acs_result` вызывает `pay_3ds`
- `PaRes/cres` не нужно передавать через GET query string:
  - данные длинные,
  - могут утечь в history/logs/referer,
  - безопаснее читать их из БД по `payment_id`.
- Альтернативный backend-only вариант нужно отдельно обсудить:
  - `redirect_3ds` сам вызывает `make_pay`
  - frontend на `acs_result` уже не вызывает `pay_3ds`
  - это проще архитектурно, но меняет ownership финального шага.

## 3. Структурированный список задач

- [ ] Шаг 1: Упростить текущий `acs_result` flow под separate-tab и убрать зависимость от промежуточного auto-submit POST как конечного решения.
- [ ] Шаг 2: Перевести `acs_result` в отдельную GET-страницу вида `/payment/acs_result/:payment_id`.
- [ ] Шаг 3: В `redirect_3ds` после сохранения `PaRes/cres` делать redirect на `acs_result` по `payment_id`.
- [ ] Шаг 4: В `acs_result` положить в `window` данные, нужные фронту:
  - `PaRes`
  - `cres`
  - при необходимости `MD`
  - `payment_id`
- [ ] Шаг 5: Согласовать с frontend разработчиком, какой именно entrypoint нужен на `acs_result`:
  - просто `window.*` переменные,
  - или `react_component`/props.
- [ ] Шаг 6: Отдельно обсудить backend-only альтернативу:
  - вызывать `make_pay` прямо в `redirect_3ds`
  - затем редиректить клиента на страницу результата
  - сравнить плюсы и риски с frontend `pay_3ds`.

## 4. Заметки для восстановления сессии

### Текущее состояние проекта и уже выполненная работа

- Изучен backend flow оплаты картой через Uniteller, начиная с `app/controllers/papi/v3/payments_controller.rb`.
- Разобрано, что до фактической заморозки денег идет последовательность:
  - создание `Payment`
  - `iacheck`
  - при необходимости `iareq`
  - challenge в ACS
  - затем `pay_3ds` -> `make_pay` -> callback `authorized`
- Проверены реальные Redash-логи платежа `1874595` в `payment_logs`:
  - это был `3DS v2 challenge`
  - цепочка: `iacheck -> iareq -> ACS challenge -> iapay(CRes) -> callback authorized`
- Разобран старый frontend flow:
  - `redirect_3ds` открывался внутри iframe
  - страница выставляла `window.LT_Payment3dsData`
  - внешний фронт на `onLoad` iframe читал `iframe.contentWindow.LT_Payment3dsData`
  - затем вызывал `pay_3ds`

### Что сейчас изменено в коде

- В `config/routes.rb` добавлен маршрут:
  - `post '/acs_result' => 'payment#acs_result'`
- В `PaymentController` добавлен пустой экшен `acs_result`.
- Для `acs_result` разрешен iframe через `allow_iframe_for_redirect_3ds`.
- Текущий шаблон `app/views/payment/redirect_3ds.html.haml` сейчас делает auto-submit формы на `/payment/acs_result`.
- Текущий шаблон `app/views/payment/acs_result.html.haml` выставляет:
  - `window.LT_Payment3dsData = { PaRes, cres, MD }`

### Почему текущую реализацию нужно переделать

- Она проектировалась как промежуточная прокладка без окончательной адаптации под separate-tab flow.
- Для новой отдельной вкладки правильнее не автопостить `PaRes/cres` в `POST /acs_result`, а:
  - сохранить их в `redirect_3ds`
  - затем редиректить на `GET /acs_result/:payment_id`
  - там уже читать данные из БД и отдавать фронту.

### Критически важные принятые решения

- Separate-tab flow остается frontend-driven:
  - frontend на `acs_result` вызывает `pay_3ds`
  - backend не должен пока сам вызывать `make_pay` в `redirect_3ds`
- Вариант с backend `make_pay` нужно сохранить как отдельную архитектурную альтернативу для следующего обсуждения.
- `PaRes/cres` нельзя тащить через GET query string.

### Точка продолжения

- Следующий шаг: перепроектировать текущий `acs_result` с `POST`-прокладки на `GET`-страницу результата.
- После этого отдельно обсудить второй вариант:
  - отказаться от frontend `pay_3ds`
  - и вызывать `make_pay` прямо в `redirect_3ds`.
