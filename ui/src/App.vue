<template>
  <div class="app-shell">
    <header class="topbar">
      <RouterLink to="/" class="brand">Web 论坛</RouterLink>
      <nav>
        <RouterLink to="/">首页</RouterLink>
        <RouterLink to="/profile">个人资料</RouterLink>
        <RouterLink to="/about">关于</RouterLink>
        <RouterLink to="/logout">登出</RouterLink>
      </nav>
    </header>
    <RouterView />
  </div>
</template>

<style>
* { box-sizing: border-box; } body { margin: 0; background: #f8fafc; color: #1e293b; font-family: system-ui, -apple-system, "Segoe UI", sans-serif; }
.topbar { display: flex; justify-content: space-between; align-items: center; padding: 14px max(16px, calc((100% - 1100px) / 2)); background: #0f172a; color: white; }
.brand { color: white; font-weight: 700; text-decoration: none; font-size: 1.1rem; } nav { display: flex; gap: 18px; } nav a { color: #cbd5e1; text-decoration: none; } nav a.router-link-active { color: white; }
</style>