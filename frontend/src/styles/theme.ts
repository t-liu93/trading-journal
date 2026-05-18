import type { GlobalThemeOverrides } from 'naive-ui'

/**
 * App-wide Naive UI theme overrides.
 *
 * Empty by default — Naive's light theme is used as-is. Add color / typography /
 * radius customisations here. Centralising them prevents per-component
 * overrides from leaking across the codebase.
 *
 * Common knobs (uncomment + customise):
 *
 *   common: {
 *     primaryColor:        '#5b6cff',         // brand primary
 *     primaryColorHover:   '#7484ff',
 *     primaryColorPressed: '#4a5be0',
 *     borderRadius:        '6px',
 *     fontFamily:          'Lato, system-ui, sans-serif',
 *     fontFamilyMono:      '"Fira Code", ui-monospace, monospace',
 *   },
 *   Button: {
 *     fontWeight: '500',
 *   },
 *   DataTable: {
 *     thFontWeight: '600',
 *   },
 *
 * Full reference of per-component keys:
 *   https://www.naiveui.com/en-US/light/docs/customize-theme
 */
export const themeOverrides: GlobalThemeOverrides = {}
