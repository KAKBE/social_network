---
name: По Следу
description: Тёмная карта рекомендаций друзей с одним зелёным действием.
colors:
  bg: "#111111"
  panel: "#1c1c1c"
  text: "#f4f4f4"
  muted: "#a3a3a3"
  accent: "#c6f135"
  accent-ink: "#111111"
  button-bg: "#c6f135"
  button-fg: "#111111"
  blue: "#2f6fed"
  danger: "#ff6b6b"
  field: "#0b0b0b"
  line: "#333333"
  badge: "#2c2c2c"
  bg-light: "#f4f4f1"
  panel-light: "#ffffff"
  text-light: "#1a1a1a"
  muted-light: "#5e5e5e"
  accent-light: "#547000"
  danger-light: "#c0392b"
  line-light: "#d5d5d0"
  badge-light: "#ecece8"
typography:
  body:
    fontFamily: "system-ui, -apple-system, Segoe UI, Roboto, sans-serif"
    fontSize: "16px"
    fontWeight: 400
    lineHeight: 1.4
  title:
    fontFamily: "system-ui, -apple-system, Segoe UI, Roboto, sans-serif"
    fontSize: "20px"
    fontWeight: 600
    lineHeight: 1.2
  wordmark:
    fontFamily: "system-ui, -apple-system, Segoe UI, Roboto, sans-serif"
    fontSize: "34px"
    fontWeight: 700
    lineHeight: 1.1
rounded:
  control: "10px"
  card: "14px"
spacing:
  xs: "4px"
  sm: "8px"
  md: "12px"
  lg: "16px"
components:
  button-primary:
    backgroundColor: "{colors.button-bg}"
    textColor: "{colors.button-fg}"
    rounded: "{rounded.control}"
    padding: "10px 14px"
    height: "44px"
  button-secondary:
    backgroundColor: "transparent"
    textColor: "{colors.text}"
    rounded: "{rounded.control}"
    padding: "10px 14px"
    height: "44px"
  button-danger:
    backgroundColor: "{colors.bg}"
    textColor: "{colors.danger}"
    rounded: "{rounded.control}"
    padding: "10px 14px"
    height: "44px"
  card:
    backgroundColor: "{colors.panel}"
    textColor: "{colors.text}"
    rounded: "{rounded.card}"
    padding: "12px"
---

## Overview

Рабочий экран. Карта занимает весь кадр. Лента, добавление, поиск, настройки и списки живут в колонке до 640px. Тёмная тема — обычное состояние. Светлая подменяет нейтрали и цвет акцентного текста, а кнопка главного действия остаётся светло-зелёной с тёмным текстом.

## Colors

Нейтрали: фон `#111111`, панель `#1c1c1c`, текст `#f4f4f4`, приглушённый текст `#a3a3a3`, линия `#333333`, поле `#0b0b0b`.

Акцент `#c6f135` только у активной вкладки, названия-пометки «Сохранено» и заливки главной кнопки. Текст на этой заливке всегда `#111111`, в том числе в светлой теме.

Опасное действие использует `#ff6b6b`, в светлой теме `#c0392b`, без зелёной заливки. Метка на карте остаётся `#2f6fed`.

Светлая тема: фон `#f4f4f1`, панель `#ffffff`, текст `#1a1a1a`, приглушённый `#5e5e5e`, акцент текста `#547000`, линия `#d5d5d0`.

## Typography

Системный шрифт без подключения отдельного семейства. Заголовок экрана 20px, название места 16px, поля не меньше 16px. Надпись входа «По Следу» 34px цветом текста, не акцентом.

## Layout

Шапка 48px: название, короткий бейдж числа рекомендаций, поиск, имя, выход. Полный замер скорости открывается в панели по бейджу.

Основной путь: карта, затем карточка места, затем страница рекомендации. Лента — второй путь, с фильтром города и автора над карточками.

Нижние вкладки повторяют колонку 640px и стоят по центру. Карта под ними остаётся на всю ширину.

## Elevation & Depth

Карточка отделяется заливкой панели и рамкой в цвет линии. Плавающие панель замера и тост лежат выше карты. Тень есть только у панели, которая перекрывает экран.

## Shapes

Карточка и мини-карта — 14px. Кнопки, поля и фото внутри карточки — 10px.

## Components

На экране одна залитая кнопка: войти, показать, опубликовать или сохранить черновик, сохранить правку, сохранить настройки, принять заявку. Пока идёт добавление в список, залита «Добавить», а «Создать» остаётся тихой. Остальные кнопки без заливки, с рамкой. «Удалить» — опасное действие. Текстовые кнопки шапки и «Назад» без рамки.

Пустая лента — блок с дословной фразой «Рекомендаций нет, но вы можете добавить свою».

## Do's and Don'ts

Зелёный не красит сразу название, все кнопки и все ссылки.

Светлая тема не оставляет тёмный текст на тёмно-зелёной кнопке и не зашивает рамки цветом тёмной темы.

Фраза пустой ленты не переписывается.

Новый шрифт, Tailwind и набор иконок не подключаются.
