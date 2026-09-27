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
        <input v-model="filters.keyword" placeholder="按元数据编号检索" />
      </label>
      <label class="filter-item">
        <span>元数据状态</span>
        <select v-model="filters.status">
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
          <td v-for="column in columns" :key="column">{{ row[column] ?? '—' }}</td>
          <td class="row-actions">
            <button class="link" type="button" @click="openDetail(row)">详情</button>
            <span v-if="isTerminal(row)" class="terminal-hint">终态不可操作</span>
            <template v-else>
              <button
                v-for="action in actions"
                :key="action"
                class="link"
                type="button"
                @click="runAction(action, row)"
              >
                {{ action }}
              </button>
            </template>
          </td>
        </tr>
        <tr v-if="!rows.length">
          <td :colspan="columns.length + 1" class="empty-state">暂无元数据登记数据，可先登记元数据记录</td>
        </tr>
      </tbody>
    </table>

    <footer class="page-foot">
      <span>共 {{ total }} 条元数据登记记录</span>
      <span v-if="noticeMessage" class="notice-text">{{ noticeMessage }}</span>
      <span v-if="errorMessage" class="error-text">{{ errorMessage }}</span>
    </footer>

    <div v-if="createVisible" class="dialog-mask" @click.self="closeCreate">
      <div class="dialog">
        <h3 class="dialog-title">登记元数据记录</h3>
        <form class="dialog-form" @submit.prevent="submitCreate">
          <label v-for="field in createFields" :key="field.key" class="dialog-item">
            <span>{{ field.label }}<em v-if="field.required" class="required-mark">*</em></span>
            <input v-model="createForm[field.key]" :placeholder="field.placeholder" />
          </label>
          <p v-if="createError" class="error-text">{{ createError }}</p>
          <div class="dialog-actions">
            <button class="btn primary" type="submit" :disabled="submitting">
              {{ submitting ? '提交中…' : createError ? '重试登记' : '提交登记' }}
            </button>
            <button class="btn ghost" type="button" @click="closeCreate">取消</button>
          </div>
        </form>
      </div>
    </div>

    <div v-if="detail" class="dialog-mask" @click.self="closeDetail">
      <div class="dialog wide">
        <h3 class="dialog-title">元数据记录详情 · {{ detail['元数据编号'] ?? detail.id }}</h3>
        <dl class="detail-grid">
          <template v-for="column in columns" :key="column">
            <dt>{{ column }}</dt>
            <dd>{{ detail[column] ?? '—' }}</dd>
          </template>
        </dl>
        <h4 class="dialog-subtitle">版本历史</h4>
        <table v-if="versions.length" class="data-table">
          <thead>
            <tr>
              <th v-for="column in versionColumns" :key="column">{{ column }}</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="(version, index) in versions" :key="index">
              <td v-for="column in versionColumns" :key="column">{{ version[column] ?? '—' }}</td>
            </tr>
          </tbody>
        </table>
        <p v-else class="empty-state">该记录暂无版本数据，确认生效后会生成第一条版本记录</p>
        <div class="dialog-actions">
          <button class="btn" type="button" @click="closeDetail">关闭</button>
        </div>
      </div>
    </div>
  </section>
</template>

<script setup lang="ts">
import { onMounted, ref } from 'vue'

import { request } from '@/api/client'

type Row = Record<string, string | number | null>

const ENDPOINT = '/api/metainfo'
const columns = ["元数据编号", "关联站点", "元数据类型", "版本号", "变更内容", "登记人员", "生效日期", "元数据状态"]
const versionColumns = ["版本号", "变更内容", "登记人员", "生效日期", "动作"]
const actions = ["提交登记", "确认生效", "作废记录"]
const statuses = ["待登记", "待补充", "已生效", "已作废"]
const terminalStatuses = ["已生效", "已作废"]
const stats = [{"label": "待登记元数据", "value": 0}, {"label": "本月生效数", "value": 0}, {"label": "待补充记录", "value": 0}]
const createFields = [
  { key: '元数据编号', label: '元数据编号', required: true, placeholder: '如 META-0005' },
  { key: '关联站点', label: '关联站点', required: true, placeholder: '如 长春国家气候观象台' },
  { key: '元数据类型', label: '元数据类型', required: true, placeholder: '如 站点信息' },
  { key: '版本号', label: '版本号', required: false, placeholder: '留空默认 V1.0' },
  { key: '变更内容', label: '变更内容', required: false, placeholder: '本次登记说明' },
  { key: '登记人员', label: '登记人员', required: false, placeholder: '登记人姓名' },
]

const rows = ref<Row[]>([])
const total = ref(0)
const errorMessage = ref('')
const noticeMessage = ref('')
const filters = ref({ keyword: '', status: '' })

const createVisible = ref(false)
const createForm = ref<Record<string, string>>({})
const createError = ref('')
const submitting = ref(false)

const detail = ref<Row | null>(null)
const versions = ref<Row[]>([])

function isTerminal(row: Row) {
  return terminalStatuses.includes(String(row['元数据状态'] ?? ''))
}

function resetFilters() {
  filters.value = { keyword: '', status: '' }
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

function closeCreate() {
  createVisible.value = false
}

async function submitCreate() {
  createError.value = ''
  submitting.value = true
  try {
    const response = await request(ENDPOINT, {
      method: 'POST',
      body: JSON.stringify({ values: { ...createForm.value } }),
    })
    const payload = await response.json()
    if (!response.ok || !payload.ok) {
      throw new Error(payload.message ?? '登记失败，请检查必填项后重试')
    }
    createVisible.value = false
    errorMessage.value = ''
    noticeMessage.value = payload.message ?? '元数据记录已登记'
    await reload()
  } catch (error) {
    // 登记失败时保留表单内容，指明原因后可直接重试
    createError.value = error instanceof Error ? error.message : '登记失败，请稍后重试'
  } finally {
    submitting.value = false
  }
}

async function runAction(action: string, row: Row) {
  errorMessage.value = ''
  noticeMessage.value = ''
  try {
    const response = await request(`${ENDPOINT}/${row.id}/actions`, {
      method: 'POST',
      body: JSON.stringify({ values: { action } }),
    })
    const payload = await response.json()
    if (!response.ok || !payload.ok) {
      throw new Error(payload.message ?? '元数据登记动作未生效，请稍后重试')
    }
    noticeMessage.value = payload.message ?? `元数据记录已${action}`
    await reload()
    if (detail.value && detail.value.id === row.id) {
      await openDetail(row)
    }
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '元数据登记操作失败'
  }
}

async function openDetail(row: Row) {
  errorMessage.value = ''
  try {
    const [detailResponse, versionsResponse] = await Promise.all([
      request(`${ENDPOINT}/${row.id}`),
      request(`${ENDPOINT}/${row.id}/versions`),
    ])
    if (!detailResponse.ok || !versionsResponse.ok) {
      throw new Error('元数据记录详情读取失败，请稍后重试')
    }
    detail.value = await detailResponse.json()
    const payload = await versionsResponse.json()
    versions.value = payload.items ?? []
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '元数据记录详情读取失败'
  }
}

function closeDetail() {
  detail.value = null
  versions.value = []
}

async function reload() {
  errorMessage.value = ''
  const query = new URLSearchParams()
  if (filters.value.keyword.trim()) {
    query.set('keyword', filters.value.keyword.trim())
  }
  if (filters.value.status) {
    query.set('status', filters.value.status)
  }
  try {
    const response = await request(`${ENDPOINT}?${query.toString()}`)
    if (!response.ok) {
      throw new Error('元数据记录列表读取失败')
    }
    const payload = await response.json()
    rows.value = payload.items ?? []
    total.value = payload.total ?? rows.value.length
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '元数据登记列表读取失败'
  }
}

onMounted(reload)
</script>

<style scoped>
.dialog-mask {
  position: fixed;
  inset: 0;
  background: rgba(15, 23, 42, 0.45);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 20;
}
.dialog {
  background: #fff;
  border-radius: 10px;
  padding: 20px 24px;
  width: 420px;
  max-width: 92vw;
  max-height: 86vh;
  overflow: auto;
  box-shadow: 0 12px 32px rgba(15, 23, 42, 0.18);
}
.dialog.wide {
  width: 640px;
}
.dialog-title {
  margin: 0 0 12px;
  font-size: 16px;
}
.dialog-subtitle {
  margin: 16px 0 8px;
  font-size: 14px;
}
.dialog-form {
  display: flex;
  flex-direction: column;
  gap: 10px;
}
.dialog-item span {
  display: block;
  font-size: 12px;
  color: var(--muted);
  margin-bottom: 4px;
}
.dialog-item input {
  width: 100%;
  border: 1px solid var(--border);
  border-radius: 6px;
  padding: 6px 10px;
  font-size: 13px;
}
.required-mark {
  color: #b42318;
  font-style: normal;
  margin-left: 2px;
}
.dialog-actions {
  display: flex;
  gap: 8px;
  justify-content: flex-end;
  margin-top: 12px;
}
.detail-grid {
  display: grid;
  grid-template-columns: 96px 1fr 96px 1fr;
  gap: 6px 12px;
  margin: 0;
  font-size: 13px;
}
.detail-grid dt {
  color: var(--muted);
}
.detail-grid dd {
  margin: 0;
}
.filter-item select {
  border: 1px solid var(--border);
  border-radius: 6px;
  padding: 5px 8px;
  font-size: 13px;
  background: #fff;
}
.terminal-hint {
  color: var(--muted);
  font-size: 12px;
}
.notice-text {
  color: #067647;
}
</style>
