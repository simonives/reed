import { defineConfig } from 'vitepress'

export default defineConfig({
  title: 'Reed',
  description: 'A self-hosted, open-source RSS reader with a graph-native data model, REST API, and MCP server.',
  themeConfig: {
    nav: [
      { text: 'Home', link: '/' },
      { text: 'Docs', link: '/docs/' },
      { text: 'GitHub', link: 'https://github.com/simonives/reed' },
    ],
  },
})
