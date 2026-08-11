import type { IntelligenceDataStatus, RiskLevel, Vessel } from './types'

const messages = {
  'common.details': 'Подробнее',
  'common.close': 'Закрыть',
  'common.open': 'Открыть',
  'common.live': 'В реальном времени',
  'common.updated': 'Обновлено',
  'map.environmentalEvents': 'Экологические события',
  'map.pollutionAreas': 'Области загрязнения',
  'map.askAssistant': 'Спросить ИИ-помощника',
  'risk.explanation': 'Почему такая оценка?',
  'risk.allFactors': 'Все факторы и доказательства',
} as const

export type MessageKey = keyof typeof messages
export function t(key: MessageKey) { return messages[key] }

const navigationStatuses: Record<Vessel['navigationStatus'], string> = {
  Underway: 'В пути',
  'At anchor': 'На якоре',
  Moored: 'У причала',
  Stopped: 'Остановлено',
  Unknown: 'Неизвестно',
}

const vesselTypes: Record<string, string> = {
  'Cargo vessel': 'Грузовое судно',
  'Oil tanker': 'Нефтяной танкер',
  'General cargo': 'Сухогруз',
  'Ro-Ro cargo': 'Ролкер',
  'Container ship': 'Контейнеровоз',
  'Bulk carrier': 'Балкер',
  'Oil products tanker': 'Танкер-нефтепродуктовоз',
  'Offshore supply': 'Судно снабжения',
  'River-sea cargo': 'Судно река-море',
  'Rail ferry': 'Железнодорожный паром',
  'Chemical tanker': 'Химический танкер',
  'Dry cargo': 'Сухогруз',
}

const countries: Record<string, string> = {
  Kazakhstan: 'Казахстан', Azerbaijan: 'Азербайджан', Russia: 'Россия',
  Turkmenistan: 'Туркменистан', Iran: 'Иран',
}

const riskLevels: Record<RiskLevel, string> = {
  LOW: 'НИЗКИЙ', MODERATE: 'УМЕРЕННЫЙ', HIGH: 'ВЫСОКИЙ', CRITICAL: 'КРИТИЧЕСКИЙ',
}

const dataStatuses: Record<IntelligenceDataStatus, string> = {
  REPORTED: 'ЗАЯВЛЕНО', ESTIMATED: 'РАСЧЁТ', VERIFIED: 'ПРОВЕРЕНО',
}

const confidences: Record<string, string> = {
  LOW: 'НИЗКАЯ', MEDIUM: 'СРЕДНЯЯ', HIGH: 'ВЫСОКАЯ',
}

export function navigationStatusLabel(status: Vessel['navigationStatus']) { return navigationStatuses[status] }
export function vesselTypeLabel(type: string) { return vesselTypes[type] || type }
export function countryLabel(country: string) { return countries[country] || country }
export function riskLevelLabel(level: RiskLevel) { return riskLevels[level] }
export function dataStatusLabel(status: IntelligenceDataStatus) { return dataStatuses[status] }
export function confidenceLabel(value: string) { return confidences[value] || value }
export function etaLabel(value: string) { return value === 'Arrived' ? 'Прибыло' : value }

const statusLabels: Record<string, string> = {
  OPEN: 'ОТКРЫТО', CLOSED: 'ЗАКРЫТО', ACTIVE: 'АКТИВНО', RECENT: 'НЕДАВНЕЕ',
  REVIEWED: 'ПРОСМОТРЕНО', COMPLETED: 'ЗАВЕРШЕНО', PENDING: 'ОЖИДАЕТ',
  ACTUAL: 'ФАКТ', PREDICTED: 'ПРОГНОЗ', PLANNED: 'ПЛАН', APPROACHING: 'ПОДХОДИТ',
  COMPATIBLE: 'СОВМЕСТИМО', NOT_COMPATIBLE: 'НЕСОВМЕСТИМО',
  FACT: 'ФАКТ', ESTIMATE: 'ОЦЕНКА', INFERENCE: 'ВЫВОД',
}

const severityLabels: Record<string, string> = {
  low: 'НИЗКАЯ', medium: 'СРЕДНЯЯ', high: 'ВЫСОКАЯ', critical: 'КРИТИЧЕСКАЯ',
}

export function statusLabel(value: string) { return statusLabels[value.toUpperCase()] || value }
export function severityLabel(value: string) { return severityLabels[value.toLowerCase()] || value }

export function relativeTimeLabel(value: string) {
  return value
    .replace('just now', 'только что')
    .replace(/(\d+) min ago/, '$1 мин назад')
    .replace(/(\d+) h ago/, '$1 ч назад')
}

export function operationalText(value: string) {
  return value
    .replaceAll('Cargo vessel', 'Грузовое судно')
    .replaceAll('Oil tanker', 'Нефтяной танкер')
    .replaceAll('Reported owner / operator', 'Заявленный владелец / оператор')
    .replaceAll('Reported owner party', 'Заявленная сторона-владелец')
    .replaceAll('Departure port', 'Порт отправления')
    .replaceAll('Destination port', 'Порт назначения')
    .replaceAll('Commercial seaport', 'Торговый морской порт')
    .replaceAll('International seaport', 'Международный морской порт')
    .replaceAll('River-sea port', 'Порт река-море')
    .replaceAll('Free zone port', 'Порт свободной зоны')
    .replaceAll('Special economic port', 'Порт специальной экономической зоны')
    .replaceAll('Logistics hub', 'Логистический узел')
    .replaceAll('General cargo', 'Генеральные грузы')
    .replaceAll('Containers', 'Контейнеры')
    .replaceAll('Passenger', 'Пассажирские перевозки')
    .replaceAll('Rail ferry', 'Железнодорожный паром')
    .replaceAll('Dry cargo', 'Сухие грузы')
    .replaceAll('Kazakhstan', 'Казахстан')
    .replaceAll('Azerbaijan', 'Азербайджан')
    .replaceAll('Turkmenistan', 'Туркменистан')
    .replaceAll('Russia', 'Россия')
    .replaceAll('Iran', 'Иран')
    .replaceAll('Current voyage', 'Текущий рейс')
    .replaceAll('Relationship', 'Тип связи')
    .replaceAll('Confidence', 'Достоверность')
    .replaceAll('Observations', 'Наблюдения')
    .replaceAll('Duration', 'Продолжительность')
    .replaceAll('Distance', 'Дистанция')
    .replaceAll('Country', 'Страна')
    .replaceAll('Operator', 'Оператор')
    .replaceAll('Owner', 'Владелец')
    .replaceAll('Role', 'Роль')
    .replaceAll('Source', 'Источник')
    .replaceAll('Status', 'Статус')
    .replaceAll('Voyages', 'Рейсы')
    .replaceAll('Flag', 'Флаг')
    .replaceAll('APPROACHING', 'ПОДХОДИТ')
    .replaceAll('WAITING', 'ОЖИДАЕТ')
    .replaceAll('ATTENTION', 'ВНИМАНИЕ')
    .replaceAll('ON TIME', 'ПО ГРАФИКУ')
    .replaceAll('CONNECTED', 'ПОДКЛЮЧЕНО')
    .replaceAll('PARTIAL', 'ЧАСТИЧНО')
    .replaceAll('PLANNED', 'ЗАПЛАНИРОВАНО')
    .replaceAll('Open sea', 'Открытое море')
    .replaceAll('Risk', 'Риск')
    .replaceAll('encounters', 'встреч')
    .replaceAll('months', 'месяцев')
    .replaceAll('Repeated encounters', 'Повторные встречи')
    .replaceAll('Route deviation', 'Отклонение маршрута')
    .replaceAll('Late declaration', 'Поздняя декларация')
    .replaceAll('Draught change', 'Изменение осадки')
    .replaceAll('AIS gap', 'Пропуск AIS')
    .replaceAll('Encounter', 'Встреча')
    .replaceAll('Turkmenbashi', 'Туркменбаши')
    .replaceAll('Astrakhan', 'Астрахань')
    .replaceAll('Baku', 'Баку')
    .replaceAll('Aktau', 'Актау')
}
