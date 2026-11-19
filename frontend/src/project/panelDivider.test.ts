import { test } from "node:test";
import assert from "node:assert/strict";
import {
  DEFAULT_SOURCE_RATIO, MIN_SOURCE_WIDTH, clampSourceWidth, parseStoredRatio,
  separatorValues, sourceWidthFromRatio, widthAfterKey,
} from "./panelDivider";

test("divider width stays inside the panel limits", () => {
  assert.equal(clampSourceWidth(600, 1440), 600);
  assert.equal(clampSourceWidth(100, 1440), MIN_SOURCE_WIDTH);
  assert.equal(clampSourceWidth(1300, 1440), 1020);
});

test("a saved ratio is limited again when the window becomes smaller", () => {
  assert.equal(sourceWidthFromRatio(0.7, 1440), 1008);
  assert.equal(sourceWidthFromRatio(0.7, 1000), 580);
  assert.equal(sourceWidthFromRatio(0.1, 1000), MIN_SOURCE_WIDTH);
});

test("the Markdown minimum wins when both panels cannot fit", () => {
  assert.equal(sourceWidthFromRatio(0.5, 600), MIN_SOURCE_WIDTH);
});

for (const stored of [null, "", "   ", "wide", "NaN", "Infinity", "0", "1", "-0.2", "1.5"]) {
  test(`invalid stored ratio uses the default: ${JSON.stringify(stored)}`, () => {
    assert.equal(parseStoredRatio(stored), DEFAULT_SOURCE_RATIO);
  });
}

test("a valid stored ratio is kept", () => {
  assert.equal(parseStoredRatio("0.55"), 0.55);
});

test("arrow keys move the divider and Shift moves it further", () => {
  assert.equal(widthAfterKey("ArrowRight", false, 500, 1440), 524);
  assert.equal(widthAfterKey("ArrowLeft", false, 500, 1440), 476);
  assert.equal(widthAfterKey("ArrowRight", true, 500, 1440), 596);
  assert.equal(widthAfterKey("ArrowLeft", true, 500, 1440), 404);
});

test("keys cannot pass the limits, and Home and End jump to them", () => {
  assert.equal(widthAfterKey("ArrowLeft", true, 300, 1440), MIN_SOURCE_WIDTH);
  assert.equal(widthAfterKey("ArrowRight", true, 1000, 1440), 1020);
  assert.equal(widthAfterKey("Home", false, 700, 1440), MIN_SOURCE_WIDTH);
  assert.equal(widthAfterKey("End", false, 700, 1440), 1020);
});

test("other keys leave the divider alone", () => {
  assert.equal(widthAfterKey("Enter", false, 500, 1440), null);
  assert.equal(widthAfterKey("a", true, 500, 1440), null);
});

test("separator values report percentages of the available width", () => {
  assert.deepEqual(separatorValues(720, 1440), { now: 50, min: 19, max: 71 });
});
