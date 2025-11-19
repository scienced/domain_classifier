/**
 * API client service for backend communication
 */
import axios, { AxiosInstance } from 'axios'
import type { Run, ClassificationRecord, RunStatistics, PaginatedResponse } from '../types'

const API_BASE_URL = '/api'

class ApiClient {
  private client: AxiosInstance
  private token: string | null = null

  constructor() {
    this.client = axios.create({
      baseURL: API_BASE_URL,
      headers: {
        'Content-Type': 'application/json'
      }
    })

    // Add auth interceptor
    this.client.interceptors.request.use((config) => {
      if (this.token) {
        config.headers.Authorization = `Bearer ${this.token}`
      }
      return config
    })

    // Load token from localStorage
    this.token = localStorage.getItem('auth_token')
  }

  setToken(token: string) {
    this.token = token
    localStorage.setItem('auth_token', token)
  }

  clearToken() {
    this.token = null
    localStorage.removeItem('auth_token')
  }

  isAuthenticated(): boolean {
    return this.token !== null
  }

  // Auth endpoints
  async login(password: string): Promise<string> {
    const response = await this.client.post('/auth/login', { password })
    const token = response.data.access_token
    this.setToken(token)
    return token
  }

  logout() {
    this.clearToken()
  }

  // Health check
  async health(): Promise<any> {
    const response = await this.client.get('/health')
    return response.data
  }

  // Runs endpoints
  async listRuns(page: number = 1, pageSize: number = 20): Promise<PaginatedResponse<Run>> {
    const response = await this.client.get('/runs/', {
      params: { page, page_size: pageSize }
    })
    return response.data
  }

  async createRun(name: string): Promise<Run> {
    const response = await this.client.post('/runs/', { name })
    return response.data
  }

  async getRun(id: number): Promise<Run> {
    const response = await this.client.get(`/runs/${id}`)
    return response.data
  }

  async getRunStatus(id: number): Promise<any> {
    const response = await this.client.get(`/runs/${id}/status`)
    return response.data
  }

  async uploadCSV(runId: number, file: File): Promise<any> {
    const formData = new FormData()
    formData.append('file', file)
    const response = await this.client.post(`/runs/${runId}/upload`, formData, {
      headers: {
        'Content-Type': 'multipart/form-data'
      }
    })
    return response.data
  }

  async uploadDomains(runId: number, domains: string[]): Promise<any> {
    const response = await this.client.post(`/runs/${runId}/upload-json`, { domains })
    return response.data
  }

  async startRun(id: number): Promise<Run> {
    const response = await this.client.post(`/runs/${id}/start`)
    return response.data
  }

  async getRunStatistics(id: number): Promise<RunStatistics> {
    const response = await this.client.get(`/runs/${id}/statistics`)
    return response.data
  }

  async deleteRun(id: number): Promise<void> {
    await this.client.delete(`/runs/${id}`)
  }

  // Records endpoints
  async listRecords(
    runId: number,
    page: number = 1,
    pageSize: number = 50,
    filters?: any
  ): Promise<PaginatedResponse<ClassificationRecord>> {
    const response = await this.client.get(`/records/run/${runId}`, {
      params: { page, page_size: pageSize, ...filters }
    })
    return response.data
  }

  async getRecord(id: number): Promise<ClassificationRecord> {
    const response = await this.client.get(`/records/${id}`)
    return response.data
  }

  async createOverride(recordId: number, newLabel: string, userNote?: string): Promise<any> {
    const response = await this.client.post(`/records/${recordId}/override`, {
      new_label: newLabel,
      user_note: userNote
    })
    return response.data
  }

  async exportCSV(runId: number): Promise<Blob> {
    const response = await this.client.get(`/records/run/${runId}/export`, {
      responseType: 'blob'
    })
    return response.data
  }

  // API Usage endpoints
  async getUsageStatistics(days: number = 30): Promise<any> {
    const response = await this.client.get('/usage/statistics', {
      params: { days }
    })
    return response.data
  }

  async getUsageHistory(days: number = 30, provider?: string, limit: number = 100): Promise<any> {
    const response = await this.client.get('/usage/history', {
      params: { days, provider, limit }
    })
    return response.data
  }

  async getDailyBreakdown(days: number = 30): Promise<any> {
    const response = await this.client.get('/usage/daily-breakdown', {
      params: { days }
    })
    return response.data
  }
}

export const apiClient = new ApiClient()
