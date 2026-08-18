<template>
  <div>
    <h1>Vue + FastAPI 测试</h1>
    <button @click="fetchData">点我获取后端数据</button>
    <p>{{ message }}</p>
  </div>
  <hr />
  <div id="app">
    <h1>我的 Vue Router 应用</h1>
    <nav>
      <RouterLink to="/">首页</RouterLink> |
      <RouterLink to="/about">关于</RouterLink>
    </nav>
    <RouterView />
  </div>
</template>

<style>
#app { text-align: center; margin-top: 50px; }
nav { margin-bottom: 20px; }
</style>
<script>
export default {
  data() {
    return {
      message: '等待点击...'
    };
  },
  methods: {
    async fetchData() {
      try {
        const res = await fetch('/api/test');
        const data = await res.json();
        this.message = data.data;
      } catch (e) {
        this.message = '请求失败，请确认后端是否运行在 8000 端口';
      }
    }
  }
};
</script>