<template>
  <div id="reed">
    <p>Reed is running. Full UI coming in M2.</p>
  </div>
</template>

<script setup>
</script>

<style>
*, *::before, *::after {
  box-sizing: border-box;
  margin: 0;
  padding: 0;
}

body {
  font-family: system-ui, sans-serif;
  background: #0f0f0f;
  color: #e8e8e8;
}

#reed {
  display: flex;
  align-items: center;
  justify-content: center;
  height: 100vh;
  font-size: 1rem;
  opacity: 0.5;
}
</style>
