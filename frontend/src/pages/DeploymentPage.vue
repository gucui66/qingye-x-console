<template>
  <a-space direction="vertical" size="large" style="width: 100%">
    <a-card title="当前部署方式" class="panel-card">
      <a-steps :current="2" size="small">
        <a-step title="前端构建" description="先在本机用 Vite 打包 Vue 3 + Ant Design Vue" />
        <a-step title="镜像构建" description="Docker 只打包 Python 运行时和已构建的静态资源" />
        <a-step title="服务启动" description="Flask 提供 API，SPA 承担前后台完整界面" />
      </a-steps>
    </a-card>

    <a-row :gutter="[16, 16]">
      <a-col :xs="24" :xl="12">
        <a-card title="首次部署命令" class="panel-card">
          <a-typography-paragraph>第一次部署建议按下面顺序执行：</a-typography-paragraph>
          <pre class="code-block">cd qingye-x-console/frontend
npm install
npm run build

cd ..
docker compose up --build -d
docker compose ps
docker compose logs -f</pre>
          <a-alert
            type="success"
            show-icon
            message="现在 Docker 只负责 Python 运行时，前端静态资源由本机构建后一起打包。"
          />
        </a-card>
      </a-col>
      <a-col :xs="24" :xl="12">
        <a-card title="迁移到新电脑时怎么做" class="panel-card">
          <pre class="code-block">1. 复制整个 macos 目录
2. 保留 .env
3. 保留 twitter_cookies.json
4. 保留 data/ 与 output/
5. 在新电脑执行 frontend/npm install
6. 执行 frontend/npm run build
7. 回到根目录执行 docker compose up --build -d</pre>
          <a-alert
            type="warning"
            show-icon
            message="如果你最在意抓取结果和数据库，请优先备份 data/。"
          />
        </a-card>
      </a-col>
    </a-row>

    <a-card title="目录迁移重点" class="panel-card">
      <a-table class="interactive-table" :columns="columns" :data-source="rows" :pagination="false" row-key="key" :scroll="{ x: 760 }" />
    </a-card>

    <a-row :gutter="[16, 16]">
      <a-col :xs="24" :xl="12">
        <a-card title="本地开发模式" class="panel-card">
          <pre class="code-block">cd qingye-x-console/frontend
npm install
npm run dev

# 另开一个终端
cd qingye-x-console
python3 app.py</pre>
          <a-typography-paragraph>
            这种方式更适合你一边提需求、一边即时改 UI。前端热更新跑在 Vite，后端继续跑 Flask API。
          </a-typography-paragraph>
        </a-card>
      </a-col>
      <a-col :xs="24" :xl="12">
        <a-card title="你现在这套部署链路的理解" class="panel-card">
          <a-list bordered>
            <a-list-item>前端源码在 frontend/，真正上线时浏览器只读取 static/vue/ 里的打包结果。</a-list-item>
            <a-list-item>Docker 容器里不再额外安装 Node，减少镜像构建时的外部依赖。</a-list-item>
            <a-list-item>你修改完 Vue 页面后，要重新执行一次 npm run build，容器里才会拿到最新前端。</a-list-item>
            <a-list-item>后端 API、任务系统、SQLite 分片媒体库仍然由 Flask 这套 Python 服务统一管理。</a-list-item>
          </a-list>
        </a-card>
      </a-col>
    </a-row>
  </a-space>
</template>

<script setup>
const columns = [
  { title: '目录 / 文件', dataIndex: 'name', key: 'name', width: 260 },
  { title: '作用', dataIndex: 'purpose', key: 'purpose' },
  { title: '迁移建议', dataIndex: 'advice', key: 'advice' },
];

const rows = [
  {
    key: 'env',
    name: '.env',
    purpose: '保存端口、Token、Cookie 路径等环境参数',
    advice: '必须一起迁移',
  },
  {
    key: 'cookies',
    name: 'twitter_cookies.json',
    purpose: '保持网页登录态',
    advice: '如果你依赖 Cookie 登录，必须迁移',
  },
  {
    key: 'data',
    name: 'data/',
    purpose: '任务历史、管理员信息、SQLite 分片媒体库',
    advice: '最优先备份',
  },
  {
    key: 'output',
    name: 'output/',
    purpose: '兼容旧结构、文档导出和历史输出',
    advice: '建议迁移',
  },
];
</script>
