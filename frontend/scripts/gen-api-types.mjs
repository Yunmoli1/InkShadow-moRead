// B5: 从后端 FastAPI 的 OpenAPI 规范生成 TS 类型（零漂移契约）。
// 用法：pnpm gen:api
// 先用 app.openapi() 离线导出 spec（无需启动服务），再交给 openapi-typescript。
import { execSync } from 'node:child_process'
import { mkdirSync, writeFileSync } from 'node:fs'
import { dirname, join } from 'node:path'
import { fileURLToPath } from 'node:url'
import openapiTS, { astToString } from 'openapi-typescript'

const here = dirname(fileURLToPath(import.meta.url))
const frontendRoot = join(here, '..')
const backendRoot = join(frontendRoot, '..', 'backend')

const dump = 'from app.main import app; import json, sys; json.dump(app.openapi(), sys.stdout)'
const stdout = execSync(`python -c "${dump}"`, { cwd: backendRoot, encoding: 'utf8', maxBuffer: 64 * 1024 * 1024 })
const spec = JSON.parse(stdout)

const ast = await openapiTS(spec)
const contents = astToString(ast)
const out = join(frontendRoot, 'src', 'lib', 'api-types.ts')
mkdirSync(dirname(out), { recursive: true })
writeFileSync(out, `// 自动生成：pnpm gen:api（来源 backend/app OpenAPI）——请勿手改\n${contents}`, 'utf8')
console.log(`generated ${out} (${contents.length} bytes, ${Object.keys(spec.components?.schemas || {}).length} schemas)`)
