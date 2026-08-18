<template>
  <div>
    <h1>Vue + FastAPI 测试</h1>
    <button @click="fetchData">点我获取后端数据</button>
    <p>{{ message }}</p>
  </div>
</template>

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
        const res = await fetch('http://127.0.0.1:8000/api/test');
        const data = await res.json();
        this.message = data.data;
      } catch (e) {
        this.message = '请求失败，请确认后端是否运行在 8000 端口';
      }
    }
  }
};
</script>