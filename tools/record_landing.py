"""Записывает скринкаст лендинга в /out/landing.webm через headless Chromium.

Запускается в образе mcr.microsoft.com/playwright/python на сети lesson-observer_default,
обращается к dev-серверу Vite по имени контейнера http://frontend:5173.
"""
import time

from playwright.sync_api import sync_playwright

URL = "http://frontend:5173"
W, H = 1280, 720


def smooth_scroll(page, to_ratio, dur_ms):
    """Плавно прокручивает страницу к доле to_ratio высоты за dur_ms (easeInOut)."""
    page.evaluate(
        """({toRatio, dur}) => new Promise(res => {
            const start = performance.now();
            const startY = window.scrollY;
            const max = Math.max(0, document.body.scrollHeight - window.innerHeight);
            const target = max * toRatio;
            const ease = p => (p < 0.5 ? 2*p*p : 1 - Math.pow(-2*p+2, 2)/2);
            function step(now){
                const p = Math.min(1, (now - start) / dur);
                window.scrollTo(0, startY + (target - startY) * ease(p));
                if (p < 1) requestAnimationFrame(step); else res();
            }
            requestAnimationFrame(step);
        })""",
        {"toRatio": to_ratio, "dur": dur_ms},
    )


with sync_playwright() as p:
    browser = p.chromium.launch(args=["--no-sandbox", "--force-color-profile=srgb"])
    context = browser.new_context(
        viewport={"width": W, "height": H},
        record_video_dir="/out",
        record_video_size={"width": W, "height": H},
    )
    page = context.new_page()
    page.goto(URL, wait_until="networkidle", timeout=60000)
    page.wait_for_selector(".lp-title", timeout=30000)
    video = page.video

    time.sleep(5.5)                  # герой: pop-анимации + печать темы + раскрытие артефактов
    smooth_scroll(page, 1.0, 10000)  # плавно вниз — триггерим scroll-reveal и count-up
    time.sleep(2.0)                  # держим финальный CTA
    smooth_scroll(page, 0.16, 5000)  # назад вверх к пайплайну
    time.sleep(1.0)

    context.close()                  # финализирует видеофайл
    browser.close()
    video.save_as("/out/landing.webm")
    print("SAVED:", video.path())
