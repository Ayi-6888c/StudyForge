"""Optional Playwright test. Synthetic learner; blocks all non-local requests."""
import os
from pathlib import Path
import tempfile

from playwright.sync_api import sync_playwright
from support import Client, Server


def main():
    errors, outside = [], []
    output = os.environ.get('STUDYFORGE_SCREENSHOT_DIR')
    if output:
        Path(output).mkdir(parents=True, exist_ok=True)
    with Server() as server:
        client = Client(server.url)
        client.ok('/api/auth/register', dict(username='demo_learner', display_name='小予', password='Test-only-2026'))
        cat = client.ok('/api/catalog?source=510203&year=2027')
        client.ok('/api/student/route', dict(province='hubei', source_code='510203', offering_id='hb-04-080901',
                  catalog_revision=cat['revision'], target_year=2027, start_date='2026-10-25',
                  deadline='2026-11-22', intensity='standard', daily_minutes=270,
                  acknowledged=True, generate_plan=True))
        before = client.ok('/api/export')
        with sync_playwright() as play:
            options = {'headless':True}
            channel = os.environ.get('STUDYFORGE_BROWSER_CHANNEL')
            if channel:
                options['channel'] = channel
            browser = play.chromium.launch(**options)
            context = browser.new_context(viewport={'width':1440, 'height':1000})
            context.add_cookies([{'name':cookie.name, 'value':cookie.value, 'url':server.url} for cookie in client.cookies])
            def guard(route):
                if route.request.url.startswith(server.url):
                    route.continue_()
                else:
                    outside.append(route.request.url)
                    route.abort()
            context.route('**/*', guard)
            page = context.new_page()
            page.on('pageerror', lambda error: errors.append(str(error)))
            page.goto(server.url+'?view=today', wait_until='networkidle')
            page.wait_for_function('quiet.bound && window.examReady')
            assert page.locator('#nav > .nav-item').count() == 6
            if output:
                page.screenshot(path=str(Path(output)/'study-desk.png'))
            page.locator('#nav [data-view=companion]').click()
            page.wait_for_selector('.news-card')
            assert page.locator('.news-card').count() == 5
            page.locator('#newsCurrentOnly').check()
            assert page.locator('.news-card').count() == 0
            page.locator('#newsCurrentOnly').uncheck()
            page.locator('#tabTutor').click()
            assert page.locator('#tutorMode option[value=local_ai]').evaluate('e=>e.disabled')
            page.locator('[data-tutor-question]').first.click()
            page.locator('#sendTutor').click()
            page.wait_for_selector('.tutor-answer')
            answer = page.locator('.tutor-answer').inner_text()
            assert '高级语言程序设计' in answer and '2027年正式要求尚未录入' in answer
            if output:
                page.evaluate('window.scrollTo(0,0)')
                page.screenshot(path=str(Path(output)/'companion.png'))
            page.locator('#tabFeedback').click()
            page.locator('#feedbackContent').fill('合成反馈<script>window.xss=1</script>')
            page.locator('#feedbackForm button').click()
            page.wait_for_function('document.querySelector("#feedbackStatus").textContent.includes("已保存")')
            assert not page.evaluate('window.xss')
            for width in (1440, 960, 768, 390, 360):
                page.set_viewport_size({'width':width, 'height':844})
                page.wait_for_timeout(100)
                assert page.evaluate('document.documentElement.scrollWidth<=innerWidth'), width
            page.locator('#tabNews').focus()
            page.keyboard.press('ArrowRight')
            assert page.locator('#tabTutor').get_attribute('aria-selected') == 'true'
            assert client.ok('/api/export') == before
            assert not errors, errors
            assert not outside, outside
            context.close()
            browser.close()
    print('UI PASS: six labelled entries; route/news/year guard; disabled AI; reference Q&A; feedback escaping; 360-1440 responsive; keyboard; zero JS errors/external requests; learning records unchanged')


if __name__ == '__main__':
    main()
