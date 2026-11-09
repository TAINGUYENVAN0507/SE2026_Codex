import axe from 'axe-core'
import { writeFileSync } from 'node:fs'
import { test, expect } from '../fixtures.js'
import { uploadMeeting, expectReady } from '../meeting.js'

for (const kind of ['list', 'upload', 'detail', 'settings'] as const) {
  test(`FE-16 axe Chromium: ${kind}, desktop và mobile`, async ({
    page,
  }, testInfo) => {
    if (kind === 'upload') {
      await page.goto('/meetings/new')
      await expect(
        page.getByLabel('Chọn file audio', { exact: true }),
      ).toBeEnabled()
    } else if (kind === 'settings') {
      await page.goto('/settings')
      await expect(page.locator('.settings-profile')).toContainText(
        'demo@meeting.local',
      )
    } else if (kind === 'detail') {
      await uploadMeeting(page, 'E2E accessibility tổng hợp', 30)
      await expectReady(page)
      await expect(
        page.getByRole('heading', { name: 'Tổng quan', exact: true }),
      ).toBeVisible()
    } else {
      await expect(
        page.getByRole('heading', { name: 'Cuộc họp', exact: true }),
      ).toBeVisible()
    }
    for (const width of [1280, 360]) {
      await page.setViewportSize({ width, height: 900 })
      await page.addScriptTag({ content: axe.source })
      await page.evaluate(() => document.fonts.ready.then(() => undefined))
      const result = await page.evaluate(async () =>
        (window as typeof window & { axe: typeof axe }).axe.run(document),
      )
      const evidence = testInfo.outputPath(`axe-${kind}-${width}.json`)
      writeFileSync(
        evidence,
        JSON.stringify(
          {
            url: page.url(),
            width,
            violations: result.violations,
            incomplete: result.incomplete,
          },
          null,
          2,
        ),
      )
      await testInfo.attach(`axe-${kind}-${width}.json`, {
        body: JSON.stringify(
          {
            url: page.url(),
            width,
            violations: result.violations,
            incomplete: result.incomplete,
          },
          null,
          2,
        ),
        contentType: 'application/json',
      })
      await page.screenshot({
        path: testInfo.outputPath(`page-${kind}-${width}.png`),
        fullPage: true,
      })
      const blocking = result.violations.filter(
        (v) => v.impact === 'serious' || v.impact === 'critical',
      )
      expect(
        blocking.map((v) => ({
          id: v.id,
          impact: v.impact,
          nodes: v.nodes.map((n) => ({
            target: n.target,
            summary: n.failureSummary,
          })),
        })),
      ).toEqual([])
      expect(
        await page.evaluate(
          () => document.documentElement.scrollWidth <= window.innerWidth,
        ),
      ).toBe(true)
    }
  })
}
