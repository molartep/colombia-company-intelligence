import fs from 'node:fs'
import path from 'node:path'
import ts from 'typescript'
import en from './i18n/locales/en.json'

// Proper names, source quotations, identifiers and units are intentionally invariant.
const invariant = new Set([
  'COLOMBIA',
  'Colombia Company Intelligence',
  'ISIN',
  'ISIN:',
  'ANN:',
  'RNVE:',
  'NIT',
  'NIT:',
  'CIIU:',
  'BVC',
  'Acciones ordinarias',
  'FastAPI',
  'React + TypeScript',
  'GitHub',
  'LinkedIn',
])
const uiAttributes = new Set([
  'aria-label',
  'aria-description',
  'title',
  'placeholder',
  'alt',
  'label',
])
const files = (dir: string): string[] =>
  fs.readdirSync(dir, { withFileTypes: true }).flatMap((entry) => {
    const file = path.join(dir, entry.name)
    return entry.isDirectory()
      ? files(file)
      : /\.tsx$/.test(file) && !/\.test\./.test(file)
        ? [file]
        : []
  })

test('JSX text and accessible UI attributes use translation keys', () => {
  const violations: string[] = []
  for (const file of files(path.resolve('src'))) {
    const source = ts.createSourceFile(
      file,
      fs.readFileSync(file, 'utf8'),
      ts.ScriptTarget.Latest,
      true,
      ts.ScriptKind.TSX,
    )
    function visit(node: ts.Node) {
      let text = ''
      if (ts.isJsxText(node)) text = node.text.replace(/\s+/g, ' ').trim()
      if (
        ts.isJsxAttribute(node) &&
        uiAttributes.has(node.name.getText(source)) &&
        node.initializer &&
        ts.isStringLiteral(node.initializer)
      )
        text = node.initializer.text
      if (/[\p{L}]/u.test(text) && !invariant.has(text))
        violations.push(
          `${path.basename(file)}:${source.getLineAndCharacterOfPosition(node.getStart(source)).line + 1}: ${text}`,
        )
      ts.forEachChild(node, visit)
    }
    visit(source)
  }
  expect(violations).toEqual([])
})

test('all literal translation keys resolve to a catalog entry', () => {
  const missing: string[] = []
  for (const file of files(path.resolve('src'))) {
    const source = ts.createSourceFile(
      file,
      fs.readFileSync(file, 'utf8'),
      ts.ScriptTarget.Latest,
      true,
      ts.ScriptKind.TSX,
    )
    function visit(node: ts.Node) {
      if (
        ts.isCallExpression(node) &&
        ts.isIdentifier(node.expression) &&
        node.expression.text === 't' &&
        node.arguments[0] &&
        ts.isStringLiteral(node.arguments[0])
      ) {
        const key = node.arguments[0].text
        const value = key
          .split('.')
          .reduce<unknown>(
            (result, segment) =>
              result && typeof result === 'object'
                ? (result as Record<string, unknown>)[segment]
                : undefined,
            en,
          )
        // i18next plural keys are resolved from the base key plus a CLDR suffix.
        const plural = key
          .split('.')
          .reduce<unknown>(
            (result, segment, i, all) =>
              result && typeof result === 'object'
                ? (result as Record<string, unknown>)[
                    segment + (i === all.length - 1 ? '_other' : '')
                  ]
                : undefined,
            en,
          )
        if (!value && !plural) missing.push(`${file}: ${key}`)
      }
      ts.forEachChild(node, visit)
    }
    visit(source)
  }
  expect(missing).toEqual([])
})
