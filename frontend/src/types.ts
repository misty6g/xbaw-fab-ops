export interface Summary {
  window_hours: number;
  as_of: string;
  lots_completed: number;
  lots_wip: number;
  lots_hold: number;
  lots_scrapped: number;
  die_yield: number | null;
  die_yield_prior: number | null;
  line_yield: number | null;
  wafer_scrap_rate: number | null;
  throughput_wph: number | null;
  open_alarms: number;
  wafers_started: number;
  wafers_scrapped: number;
  wafers_out: number;
  good_die: number;
  tested_die: number;
}

export interface YieldPoint {
  date: string;
  die_yield: number | null;
  line_yield: number | null;
  scrap_rate: number | null;
  lots: number;
  wafers_started: number;
}

export interface YieldGroup {
  key: string;
  label: string;
  die_yield: number | null;
  line_yield: number | null;
  scrap_rate: number | null;
  lots: number;
  wafers_started: number;
  wafers_out: number;
}

export interface Tool {
  id: string;
  name: string;
  area: string;
  area_label: string;
  model: string;
  state: string;
  updated_at: string | null;
  open_alarms: number;
  utilization: number | null;
  wafers_out: number;
  step_yield: number | null;
}

export interface Lot {
  id: string;
  recipe_id: string;
  recipe_name: string;
  status: string;
  current_step: string | null;
  step_label: string | null;
  current_tool_id: string | null;
  wafer_count: number;
  scrap_wafers: number;
  good_die: number;
  tested_die: number;
  die_yield: number | null;
  line_yield: number | null;
  started_at: string | null;
  completed_at: string | null;
}

export interface Alarm {
  id: number;
  tool_id: string;
  tool_name: string;
  lot_id: string | null;
  alarm_code: string;
  severity: string;
  text: string;
  set_at: string;
  cleared_at: string | null;
  open: boolean;
}

export interface ProcessEvent {
  event_id: string;
  event_type: string;
  timestamp: string;
  tool_id: string;
  lot_id: string | null;
  ceid: number | null;
  summary: string;
}

export interface SpcPoint {
  timestamp: string;
  value: number;
  lot_id: string;
  tool_id: string;
  wafer_slot: number | null;
  ooc: boolean;
  oos: boolean;
}

export interface Spc {
  metric: string;
  label: string;
  unit: string;
  recipe_id: string | null;
  n: number;
  mean: number | null;
  sigma: number | null;
  ucl: number | null;
  lcl: number | null;
  lsl: number | null;
  usl: number | null;
  target: number | null;
  cp: number | null;
  cpk: number | null;
  ooc: number;
  oos: number;
  points: SpcPoint[];
}

export interface DashboardData {
  summary: Summary;
  trend: YieldPoint[];
  recipes: YieldGroup[];
  tools: Tool[];
  lots: Lot[];
  alarms: Alarm[];
  events: ProcessEvent[];
  spc: Spc;
}
