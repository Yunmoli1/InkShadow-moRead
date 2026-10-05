// B5 领域类型：全部派生自后端 OpenAPI 生成的 api-types.ts，
// 后端契约变化时跑 `pnpm gen:api` 即可让编译期暴露漂移。
import type { components } from './api-types'

type S = components['schemas']

export type Novel = S['NovelOut']
export type Chapter = S['ChapterOut']
export type ChapterContent = S['ChapterContentOut']
export type Note = S['NoteOut']
export type Media = S['MediaOut']
export type Task = S['TaskOut']
export type ToolInfo = S['ToolOut']
export type AppSettings = S['SettingsOut']
export type TaskPageData = S['TaskPage']
