<template>
  <section class="page" data-module="metainfo">
    <header class="page-head">
      <div>
        <h2>元数据登记管理</h2>
        <p class="page-desc">维护元数据记录，围绕元数据编号、关联站点、元数据类型、版本号做登记、筛选与状态流转。</p>
      </div>
      <div class="page-actions">
        <button class="btn primary" type="button" @click="openCreate">登记元数据记录</button>
        <button class="btn" type="button" @click="exportRows">导出元数据登记清单</button>
      </div>
    </header>

    <div class="stat-row">
      <article v-for="item in stats" :key="item.label" class="stat-card">
        <span class="stat-label">{{ item.label }}</span>
        <strong class="stat-value">{{ item.value }}</strong>
      </article>
    </div>

    <form class="filter-bar" @submit.prevent="reload">
      <label class="filter-item">
        <span>元数据编号</span>
        <input v-model="keyword" placeholder="按元数据编号检索" />
      </label>
      <label class="filter-item">
        <span>元数据状态</span>
        <select v-model="statusFilter">
          <option value="">全部状态</option>
          <option v-for="status in statuses" :key="status" :value="status">{{ status }}</option>
        </select>
      </label>
      <button class="btn" type="submit">查询</button>
      <button class="btn ghost" type="button" @click="resetFilters">重置条件</button>
    </form>

    <table class="data-table">
      <thead>
        <tr>
          <th v-for="column in columns" :key="column">{{ column }}</th>
          <th>可执行动作</th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="row in rows" :key="String(row.id)">
          <td v-for="column in columns" :key="column">{{ displayValue(row[column]) }}</td>
          <td class="row-actions">
            <button class="link" type="button" @click="openDetail(row)">详情</button>
            <button
              v-for="action in actionsFor(row)"
              :key="action"
              class="link"
              type="button"
              @click="runAction(action, row)"
            >
              {{ action }}
            </button>
            <span v-if="!actionsFor(row).length" class="muted-text">终态不可操作</span>
          </td>
        </tr>
        <tr v-if="!rows.length">
          <td :colspan="columns.length + 1" class="empty-state">暂无元数据登记数据，可先登记元数据记录</td>
        </tr>
      </tbody>
    </table>

    <footer class="page-foot">
      <span>共 {{ total }} 条元数据登记记录</span>
      <span v-if="errorMessage" class="error-text">{{ errorMessage }}</span>
    </footer>

    <div v-if="createVisible" class="dialog-mask" @click.self="createVisible = false">
      <div class="dialog">
        <h3>登记元数据记录</h3>
        <form @submit.prevent="submitCreate">
          <label v-for="field in createFields" :key="field.name" class="form-item">
            <span>{{ field.label }}<em v-if="field.required" class="required-mark">*</em></span>
            <input v-model="createForm[field.name]" :placeholder="`请输入${field.label}`" />
          </label>
          <p v-if="createError" class="error-text">{{ createError }}</p>
          <div class="dialog-actions">
            <button class="btn primary" type="submit" :disabled="createSubmitting">
              {{ createSubmitting ? '提交中…' : (createError ? '重试登记' : '提交登记') }}
            </button>
            <button class="btn ghost" type="button" @click="createVisible = false">取消</button>
          </div>
        </form>
      </div>
    </div>

    <div v-if="detailVisible" class="dialog-mask" @click.self="closeDetail">
      <div class="dialog drawer">
        <template v-if="detail">
          <h3>元数据记录详情：{{ displayValue(detail['元数据编号']) }}</h3>
          <dl class="detail-grid">
            <template v-for="column in columns" :key="column">
              <dt>{{ column }}</dt>
              <dd>{{ displayValue(detail[column]) }}</dd>
            </template>
          </dl>
          <h4>版本历史</h4>
          <table v-if="versionsOf(detail).length" class="data-table">
            <thead>
              <tr>
                <th v-for="column in versionColumns" :key="column">{{ column }}</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="version in versionsOf(detail)" :key="String(version['版本号'])">
                <td v-for="column in versionColumns" :key="column">{{ displayValue(version[column]) }}</td>
              </tr>
            </tbody>
          </table>
          <p v-else class="empty-state version-empty">暂无版本数据：该记录尚未确认生效，确认生效后会生成首个版本并保留在此。</p>
          <div class="dialog-actions">
            <button
              v-for="action in actionsFor(detail)"
              :key="action"
              class="btn"
              type="button"
              @click="runAction(action, detail)"
            >
              {{ action }}
            </button>
            <button class="btn ghost" type="button" @click="closeDetail">返回列表</button>
          </div>
        </template>
        <p v-else class="empty-state">正在读取元数据记录详情…</p>
      </div>
    </div>
  </section>
</template>

<script setup lang="ts">
import { onMounted, ref } from 'vue'

import { request } from '@/api/client'

type Row = Record<string, unknown> & { id?: number }

const ENDPOINT = '/api/metainfo'
const columns = ["元数据编号", "关联站点", "元数据类型", "版本号", "变更内容", "登记人员", "生效日期", "元数据状态"]
const versionColumns = ["版本号", "变更内容", "登记人员", "生效日期", "动作"]
const statuses = ["待登记", "待补充", "已生效", "已作废"]
// 与后端状态机保持一致：终态（已生效、已作废）不再提供任何动作
const ACTIONS_BY_STATUS: Record<string, string[]> = {
  '待登记': ['提交登记', '作废记录'],
  '待补充': ['确认生效', '作废记录'],
  '已生效': [],
  '已作废': [],
}
const createFields = [
  { name: '元数据编号', label: '元数据编号', required: true },
  { name: '关联站点', label: '关联站点', required: true },
  { name: '元数据类型', label: '元数据类型', required: true },
  { name: '变更内容', label: '变更内容', required: false },
  { name: '登记人员', label: '登记人员', required: false },
]

const rows = ref<Row[]>([])
const total = ref(0)
const stats = ref([
  { label: '待登记元数据', value: 0 },
  { label: '本月生效数', value: 0 },
  { label: '待补充记录', value: 0 },
])
const errorMessage = ref('')
const keyword = ref('')
const statusFilter = ref('')

const createVisible = ref(false)
const createSubmitting = ref(false)
const createError = ref('')
const createForm = ref<Record<string, string>>({})

const detailVisible = ref(false)
const detail = ref<Row | null>(null)

function displayValue(value: unknown): string {
  if (value === null || value === undefined || value === '') return '—'
  return String(value)
}

function actionsFor(row: Row): string[] {
  return ACTIONS_BY_STATUS[String(row.status ?? '')] ?? []
}

function versionsOf(row: Row): Row[] {
  const history = row['版本历史']
  return Array.isArray(history) ? (history as Row[]) : []
}

function errorReason(payload: Record<string, unknown>, fallback: string): string {
  if (typeof payload.message === 'string' && payload.message) return payload.message
  if (typeof payload.detail === 'string' && payload.detail) return payload.detail
  return fallback
}

function resetFilters() {
  keyword.value = ''
  statusFilter.value = ''
  void reload()
}

function exportRows() {
  window.open(`${ENDPOINT}/export`, '_blank')
}

function openCreate() {
  createForm.value = {}
  createError.value = ''
  createVisible.value = true
}

async function submitCreate() {
  createError.value = ''
  createSubmitting.value = true
  try {
    const response = await request(ENDPOINT, {
      method: 'POST',
      body: JSON.stringify({ values: createForm.value }),
    })
    const payload = await response.json()
    if (!response.ok || !payload.ok) {
      // 登记失败：说明原因并保留已填内容，可直接重试
      throw new Error(errorReason(payload, '元数据记录登记失败，请稍后重试'))
    }
    createVisible.value = false
    await Promise.all([reload(), loadStats()])
  } catch (error) {
    createError.value = error instanceof Error ? error.message : '元数据记录登记失败'
  } finally {
    createSubmitting.value = false
  }
}

async function runAction(action: string, row: Row) {
  errorMessage.value = ''
  try {
    const response = await request(`${ENDPOINT}/${row.id}/actions`, {
      method: 'POST',
      body: JSON.stringify({ values: { action } }),
    })
    const payload = await response.json()
    if (!response.ok || !payload.ok) {
      throw new Error(errorReason(payload, '元数据登记动作未生效，请稍后重试'))
    }
    await Promise.all([reload(), loadStats()])
    if (detailVisible.value && detail.value?.id === row.id) {
      await refreshDetail(row.id)
    }
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '元数据登记操作失败'
  }
}

async function openDetail(row: Row) {
  detailVisible.value = true
  detail.value = null
  await refreshDetail(row.id)
}

async function refreshDetail(id: number | undefined) {
  if (id === undefined) return
  try {
    const response = await request(`${ENDPOINT}/${id}`)
    const payload = await response.json()
    if (!response.ok) {
      throw new Error(errorReason(payload, '元数据记录详情读取失败'))
    }
    detail.value = payload
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '元数据记录详情读取失败'
    detailVisible.value = false
  }
}

function closeDetail() {
  detailVisible.value = false
  detail.value = null
  // 退回列表时按同一份数据刷新，保证列表、详情与版本展示一致
  void reload()
  void loadStats()
}

async function reload() {
  errorMessage.value = ''
  const query = new URLSearchParams()
  if (keyword.value.trim()) query.set('keyword', keyword.value.trim())
  if (statusFilter.value) query.set('status', statusFilter.value)
  try {
    const response = await request(`${ENDPOINT}?${query.toString()}`)
    const payload = await response.json()
    if (!response.ok) {
      throw new Error(errorReason(payload, '元数据记录列表读取失败'))
    }
    rows.value = payload.items ?? []
    total.value = payload.total ?? rows.value.length
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '元数据登记列表读取失败'
  }
}

async function loadStats() {
  try {
    const response = await request(`${ENDPOINT}?size=200`)
    if (!response.ok) return
    const payload = await response.json()
    const all: Row[] = payload.items ?? []
    const month = new Date().toISOString().slice(0, 7)
    const effectiveThisMonth = all.reduce(
      (count, row) => count + versionsOf(row).filter((version) => String(version['生效日期'] ?? '').startsWith(month)).length,
      0,
    )
    stats.value = [
      { label: '待登记元数据', value: all.filter((row) => row.status === '待登记').length },
      { label: '本月生效数', value: effectiveThisMonth },
      { label: '待补充记录', value: all.filter((row) => row.status === '待补充').length },
    ]
  } catch {
    // 统计卡片读取失败不阻断列表展示
  }
}

onMounted(() => {
  void reload()
  void loadStats()
})
</script>

<style scoped>
.filter-item select,
.form-item input {
  border: 1px solid var(--border);
  border-radius: 6px;
  padding: 6px 8px;
  font-size: 13px;
  min-width: 160px;
}
.muted-text { color: var(--muted); font-size: 12px; }
.dialog-mask {
  position: fixed;
  inset: 0;
  background: rgba(15, 23, 42, 0.45);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 10;
}
.dialog {
  background: #fff;
  border-radius: 10px;
  padding: 20px;
  width: 420px;
  max-height: 85vh;
  overflow: auto;
}
.dialog.drawer { width: 640px; }
.dialog h3 { margin: 0 0 12px; }
.dialog h4 { margin: 16px 0 8px; }
.form-item { display: block; margin-bottom: 10px; }
.form-item span { display: block; font-size: 12px; color: var(--muted); margin-bottom: 4px; }
.form-item input { width: 100%; }
.required-mark { color: #b42318; font-style: normal; margin-left: 2px; }
.dialog-actions { display: flex; gap: 8px; margin-top: 14px; }
.detail-grid {
  display: grid;
  grid-template-columns: 96px 1fr 96px 1fr;
  gap: 6px 12px;
  margin: 0;
  font-size: 13px;
}
.detail-grid dt { color: var(--muted); }
.detail-grid dd { margin: 0; }
.version-empty { padding: 12px 0; }
</style>
