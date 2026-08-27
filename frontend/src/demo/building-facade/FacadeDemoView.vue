<script setup lang="ts">
import { useRouter } from 'vue-router'
import BuildingFacade3D from './BuildingFacade3D.vue'

const router = useRouter()
</script>

<template>
  <div class="facade-demo-page">
    <header class="demo-header">
      <div class="demo-header-text">
        <h1>楼宇外观美化 DEMO</h1>
        <p>
          建筑轮廓 1:1 还原自 /building-viewer（building_cell 快照，含缺格与三角形切角），
          外观参考 thingraph/bim-viewer 风格：整片玻璃幕墙 + 楼层带 + 竖向分隔框 + BIM 线框。
        </p>
      </div>
      <button type="button" class="back-btn" @click="router.push('/building-viewer')">
        ← 返回原 3D 楼宇页
      </button>
    </header>
    <main class="demo-body">
      <BuildingFacade3D />
    </main>
  </div>
</template>

<style scoped>
.facade-demo-page {
  display: flex;
  flex-direction: column;
  width: 100%;
  height: calc((100vh / var(--ls-scale, 1)) - var(--ls-content-offset, 96px));
  min-height: 560px;
  overflow: hidden;
  border: 1px solid #e6e2da;
  border-radius: 2px;
}

.demo-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  padding: 10px 20px;
  background: #0d0d0d;
  border-bottom: 1px solid rgba(196, 165, 116, 0.35);
}

.demo-header-text h1 {
  margin: 0;
  font-size: 15px;
  font-weight: 650;
  color: #f5ead7;
}

.demo-header-text p {
  margin: 2px 0 0;
  font-size: 12px;
  color: rgba(255, 255, 255, 0.6);
}

.back-btn {
  flex-shrink: 0;
  padding: 6px 14px;
  font-size: 12px;
  color: #f5ead7;
  background: rgba(196, 165, 116, 0.18);
  border: 1px solid rgba(196, 165, 116, 0.55);
  border-radius: 4px;
  cursor: pointer;
  transition: background 0.15s ease;
}

.back-btn:hover {
  background: rgba(196, 165, 116, 0.32);
}

.demo-body {
  flex: 1;
  min-height: 0;
  position: relative;
}
</style>
