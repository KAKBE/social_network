"""Low-fidelity wireframes for the defense. Run: .venv\\Scripts\\python docs\\mockups\\draw_mockups.py"""

from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

OUT = Path(__file__).resolve().parent
FONT = "C:/Windows/Fonts/segoeui.ttf"
FONT_BOLD = "C:/Windows/Fonts/segoeuib.ttf"
W, H = 360, 720
GAP = 40
INK = (40, 40, 40)
LINE = (150, 150, 150)
FILL = (235, 235, 235)
ACCENT = (198, 241, 53)


def font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(FONT_BOLD if bold else FONT, size)


def box(d: ImageDraw.ImageDraw, x: int, y: int, w: int, h: int, label: str = "", fill=FILL, size: int = 14) -> None:
    d.rounded_rectangle([x, y, x + w, y + h], radius=8, outline=LINE, fill=fill, width=2)
    if label:
        d.text((x + 10, y + h / 2), label, font=font(size), fill=INK, anchor="lm")


def button(d: ImageDraw.ImageDraw, x: int, y: int, w: int, label: str) -> None:
    box(d, x, y, w, 40, fill=ACCENT)
    d.text((x + w / 2, y + 20), label, font=font(15, True), fill=INK, anchor="mm")


def frame(d: ImageDraw.ImageDraw, ox: int, title: str, status: str) -> None:
    d.rounded_rectangle([ox, 60, ox + W, 60 + H], radius=28, outline=INK, width=3, fill=(255, 255, 255))
    d.text((ox + W / 2, 30), title, font=font(18, True), fill=INK, anchor="mm")
    d.text((ox + W / 2, 60 + H + 24), status, font=font(14), fill=(120, 120, 120), anchor="mm")
    d.line([ox, 110, ox + W, 110], fill=LINE, width=1)
    d.text((ox + 16, 85), "По Следу", font=font(16, True), fill=INK, anchor="lm")


def tabbar(d: ImageDraw.ImageDraw, ox: int, active: int) -> None:
    y = 60 + H - 56
    d.line([ox, y, ox + W, y], fill=LINE, width=1)
    for i, name in enumerate(["Карта", "Лента", "Добавить", "Списки"]):
        cx = ox + W / 8 + i * W / 4
        d.text((cx, y + 28), name, font=font(14, i == active), fill=INK, anchor="mm")


def map_area(d: ImageDraw.ImageDraw, ox: int, y0: int, y1: int) -> None:
    d.rectangle([ox + 2, y0, ox + W - 2, y1], fill=(225, 232, 225))
    for i in range(6):
        d.line([ox, y0 + 40 + i * 60, ox + W, y0 + 10 + i * 70], fill=(200, 205, 200), width=6)
    for px, py in [(80, 90), (150, 160), (240, 120), (110, 260), (270, 230), (190, 320), (300, 340)]:
        d.ellipse([ox + px - 9, y0 + py - 9, ox + px + 9, y0 + py + 9], fill=ACCENT, outline=INK, width=2)
    d.text((ox + W - 8, y1 - 8), "© OpenStreetMap contributors", font=font(10), fill=INK, anchor="rb")


def screen_register(d: ImageDraw.ImageDraw, ox: int) -> None:
    frame(d, ox, "1. Регистрация (US-01)", "макет; в образце только вход тестовых пользователей")
    d.text((ox + 24, 150), "Создать аккаунт", font=font(22, True), fill=INK)
    for i, label in enumerate(["Имя", "Логин", "Пароль"]):
        d.text((ox + 24, 200 + i * 75), label, font=font(14), fill=INK)
        box(d, ox + 24, 222 + i * 75, W - 48, 40)
    button(d, ox + 24, 450, W - 48, "Зарегистрироваться")
    d.text((ox + W / 2, 515), "Уже есть аккаунт? Войти", font=font(14), fill=INK, anchor="mm")


def screen_map(d: ImageDraw.ImageDraw, ox: int) -> None:
    frame(d, ox, "2. Карта друзей (US-03, US-04)", "макет; реализовано в образце")
    map_area(d, ox, 111, 60 + H - 57)
    box(d, ox + 12, 470, W - 24, 180, fill=(250, 250, 250))
    d.text((ox + 26, 488), "Коворкинг у метро", font=font(16, True), fill=INK)
    d.text((ox + 26, 512), "Рекомендует Кристина · 11.10", font=font(13), fill=(110, 110, 110))
    d.text((ox + 26, 540), "Тихо, есть розетки, удобно", font=font(14), fill=INK)
    d.text((ox + 26, 560), "готовиться к семинарам.", font=font(14), fill=INK)
    box(d, ox + 26, 596, 150, 40, "Учёба")
    d.polygon([(ox + 150, 612), (ox + 162, 612), (ox + 156, 620)], fill=INK)
    button(d, ox + 186, 596, 150, "Сохранить")
    tabbar(d, ox, 0)


def screen_friends(d: ImageDraw.ImageDraw, ox: int) -> None:
    frame(d, ox, "3. Добавить друга (US-02)", "макет; в образце друзья заданы тестовыми данными")
    d.text((ox + 24, 140), "Друзья", font=font(22, True), fill=INK)
    box(d, ox + 24, 185, W - 130, 40, "Логин друга")
    button(d, ox + W - 96, 185, 72, "Найти")
    for i, (name, state) in enumerate([("Аня", "в друзьях"), ("Саша", "в друзьях"), ("Дима", "заявка отправлена")]):
        y = 250 + i * 64
        d.ellipse([ox + 24, y, ox + 64, y + 40], fill=FILL, outline=LINE, width=2)
        d.text((ox + 78, y + 12), name, font=font(16, True), fill=INK)
        d.text((ox + W - 24, y + 20), state, font=font(13), fill=(110, 110, 110), anchor="rm")
    tabbar(d, ox, 3)


def screen_report(d: ImageDraw.ImageDraw, ox: int) -> None:
    frame(d, ox, "4. Жалоба и модерация (US-13, US-14)", "макет; в образце не реализовано")
    d.text((ox + 24, 140), "Пожаловаться", font=font(22, True), fill=INK)
    for i, reason in enumerate(["Реклама или спам", "Оскорбительный текст", "Место не существует"]):
        y = 190 + i * 52
        d.ellipse([ox + 24, y + 8, ox + 44, y + 28], outline=INK, width=2)
        d.text((ox + 56, y + 18), reason, font=font(15), fill=INK, anchor="lm")
    button(d, ox + 24, 360, W - 48, "Отправить")
    d.line([ox + 24, 430, ox + W - 24, 430], fill=LINE, width=1)
    d.text((ox + 24, 445), "Модератор: очередь жалоб", font=font(16, True), fill=INK)
    for i in range(2):
        y = 480 + i * 80
        box(d, ox + 24, y, W - 48, 66, fill=(250, 250, 250))
        d.text((ox + 36, y + 20), f"Жалоба №{i + 1} · реклама", font=font(14), fill=INK, anchor="lm")
        d.text((ox + W - 36, y + 46), "Скрыть   Отклонить", font=font(14, True), fill=INK, anchor="rm")


def main() -> None:
    screens = [screen_register, screen_map, screen_friends, screen_report]
    image = Image.new("RGB", (GAP + len(screens) * (W + GAP), H + 120), "white")
    d = ImageDraw.Draw(image)
    for i, draw in enumerate(screens):
        draw(d, GAP + i * (W + GAP))
    image.save(OUT / "макеты_экранов.png")
    for i, draw in enumerate(screens):
        single = Image.new("RGB", (W + 2 * GAP, H + 120), "white")
        draw(ImageDraw.Draw(single), GAP)
        single.save(OUT / f"макет_{i + 1}.png")


if __name__ == "__main__":
    main()
