// ECharts 按需引入配置
// 此文件在应用启动时注册所需的图表组件，替代全量引入

import { use } from 'echarts/core'

// 渲染器
import { CanvasRenderer } from 'echarts/renderers'

// 组件
import { GridComponent } from 'echarts/components'
import { RadarComponent } from 'echarts/components'
import { TooltipComponent } from 'echarts/components'
import { LegendComponent } from 'echarts/components'
import { VisualMapComponent } from 'echarts/components'

// 图表类型
import { HeatmapChart } from 'echarts/charts'
import { RadarChart } from 'echarts/charts'
import { LineChart } from 'echarts/charts'

use([
  CanvasRenderer,
  GridComponent,
  RadarComponent,
  TooltipComponent,
  LegendComponent,
  VisualMapComponent,
  HeatmapChart,
  RadarChart,
  LineChart,
])
