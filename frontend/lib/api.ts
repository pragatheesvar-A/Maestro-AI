import axios from "axios";

export const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
export const WS_BASE = process.env.NEXT_PUBLIC_WS_URL || "ws://localhost:8000";

export const api = axios.create({ baseURL: API_BASE });

api.interceptors.request.use((config) => {
  if (typeof window !== "undefined") {
    const token = localStorage.getItem("smartalloc_token");
    if (token) {
      config.headers = config.headers || {};
      config.headers.Authorization = `Bearer ${token}`;
    }
  }
  return config;
});

api.interceptors.response.use(
  (res) => res,
  (err) => {
    if (typeof window !== "undefined" && err?.response?.status === 401) {
      localStorage.removeItem("smartalloc_token");
      if (window.location.pathname !== "/login") window.location.href = "/login";
    }
    return Promise.reject(err);
  }
);

// ---- Types ----
export interface EmployeeSkillOut { skill_name: string; proficiency: number; }
export interface Employee {
  id: string; name: string; email: string; role: string;
  experience_years: number; max_capacity_hours: number; current_workload_hours: number;
  location: string; availability_status: string; historical_performance_score: number;
  certifications: string[]; skills: EmployeeSkillOut[];
  dynamic_performance_score?: number | null;
  performance_trend?: string | null;
  performance_sample_size?: number | null;
  unavailability_risk?: number | null;
  unavailability_risk_tier?: string | null;
}
export interface TaskOut {
  id: string; title: string; description: string; priority: string;
  estimated_hours: number; deadline: string | null; sla_hours: number;
  location: string; complexity: number; project: string; status: string;
  required_skills: string[]; assigned_employee_id: string | null;
  assigned_employee_name: string | null; skill_match_score: number | null; sla_risk: number | null;
}
export interface AssignmentChange {
  task_id: string; task_title: string;
  old_employee_id: string | null; old_employee_name: string | null;
  new_employee_id: string | null; new_employee_name: string | null;
  skill_match: number; workload: number; sla_risk: number;
  reason_codes: string[]; explanation: string;
}
export interface ReallocationResult {
  trigger: string; changes: AssignmentChange[]; unresolved_task_ids: string[];
  duration_ms: number; solver_status: string; fairness_index: number;
}
export interface DashboardStats {
  total_employees: number; available_employees: number; active_tasks: number;
  assigned_tasks: number; unassigned_tasks: number; avg_sla_risk: number;
  avg_workload_utilization: number; fairness_index: number; active_disruptions: number;
}
export interface DecisionTrace {
  task_id: string; chosen_employee_id: string | null; previous_employee_id: string | null;
  trigger: string; candidates: any[]; hard_constraints_checked: string[];
  reason_codes: string[]; explanation: string; objective_breakdown: any; created_at: string;
}
export interface WorkloadItem { employee_id: string; employee_name: string; workload_hours: number; max_capacity: number; utilization: number; }
export interface FairnessAnalyticsOut { jain_fairness_index: number; gini_coefficient: number; workload_variance: number; per_employee: WorkloadItem[]; }
export interface SlaItem { task_id: string; task_title: string; sla_risk: number; predicted_completion_hours: number; deadline: string | null; priority: string; }

// ---- Auth ----
export const login = (email: string, password: string) =>
  api.post("/auth/login", { email, password }).then((r) => r.data);

// ---- Employees ----
export const getEmployees = () => api.get<Employee[]>("/employees").then((r) => r.data);
export const getEmployee = (id: string) => api.get<Employee>(`/employees/${id}`).then((r) => r.data);
export const setAvailability = (id: string, status: string, reason: string, trigger_reallocation = true) =>
  api.patch(`/employees/${id}/availability`, { status, reason, trigger_reallocation }).then((r) => r.data);
export const createEmployee = (payload: any) => api.post("/employees", payload).then((r) => r.data);

// ---- Tasks ----
export const getTasks = () => api.get<TaskOut[]>("/tasks").then((r) => r.data);
export const getTask = (id: string) => api.get<TaskOut>(`/tasks/${id}`).then((r) => r.data);
export const createTask = (payload: any) => api.post("/tasks", payload).then((r) => r.data);

// ---- Allocation ----
export const optimizeAllocation = (payload: any = {}) =>
  api.post<ReallocationResult>("/allocation/optimize", payload).then((r) => r.data);
export const triggerEmployeeUnavailable = (employee_id: string, reason: string) =>
  api.post("/events/employee-unavailable", { employee_id, reason }).then((r) => r.data);
export const getExplanation = (taskId: string) =>
  api.get(`/allocation/${taskId}/explanation`).then((r) => r.data);
export const getDecisionTrace = (taskId: string) =>
  api.get<DecisionTrace>(`/allocation/${taskId}/decision-trace`).then((r) => r.data);
export const runManagerAgent = (instruction: string) =>
  api.post("/agents/manager", { instruction }).then((r) => r.data);
export const resetDemo = () =>
  api.post("/admin/reset-demo", {}, { timeout: 60000 }).then((r) => r.data);

// ---- Analytics ----
export const getDashboardStats = () => api.get<DashboardStats>("/analytics/dashboard").then((r) => r.data);
export const getWorkloadAnalytics = () => api.get<WorkloadItem[]>("/analytics/workload").then((r) => r.data);
export const getFairnessAnalytics = () => api.get<FairnessAnalyticsOut>("/analytics/fairness").then((r) => r.data);
export const getSlaAnalytics = () => api.get<SlaItem[]>("/analytics/sla").then((r) => r.data);
export const getNotifications = () => api.get("/analytics/notifications").then((r) => r.data);
