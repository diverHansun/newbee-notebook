import * as echarts from "echarts/core";
import {
  BarChart,
  BoxplotChart,
  CandlestickChart,
  EffectScatterChart,
  FunnelChart,
  GaugeChart,
  HeatmapChart,
  LineChart,
  PieChart,
  RadarChart,
  SankeyChart,
  ScatterChart,
  SunburstChart,
  TreemapChart,
} from "echarts/charts";
import {
  DatasetComponent,
  GridComponent,
  LegendComponent,
  PolarComponent,
  RadarComponent,
  TitleComponent,
  ToolboxComponent,
  TooltipComponent,
  VisualMapComponent,
} from "echarts/components";
import { CanvasRenderer } from "echarts/renderers";

export const ECHARTS_SERIES_TYPE_WHITELIST = [
  "bar",
  "line",
  "pie",
  "scatter",
  "effectScatter",
  "radar",
  "heatmap",
  "treemap",
  "sunburst",
  "sankey",
  "gauge",
  "funnel",
  "candlestick",
  "boxplot",
] as const;

export type EChartsSeriesType = (typeof ECHARTS_SERIES_TYPE_WHITELIST)[number];

let registered = false;

export function ensureEChartsRegistered(): void {
  if (registered) return;
  echarts.use([
    BarChart,
    LineChart,
    PieChart,
    ScatterChart,
    EffectScatterChart,
    RadarChart,
    HeatmapChart,
    TreemapChart,
    SunburstChart,
    SankeyChart,
    GaugeChart,
    FunnelChart,
    CandlestickChart,
    BoxplotChart,
    GridComponent,
    TooltipComponent,
    LegendComponent,
    TitleComponent,
    RadarComponent,
    PolarComponent,
    VisualMapComponent,
    DatasetComponent,
    ToolboxComponent,
    CanvasRenderer,
  ]);
  registered = true;
}

export { echarts };
