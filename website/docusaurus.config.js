// @ts-check
import {themes as prismThemes} from 'prism-react-renderer';

/** @type {import('@docusaurus/types').Config} */
const config = {
  title: 'SPECA',
  tagline: 'Specification-to-Property Agentic Auditing',
  favicon: 'img/speca_logo.svg',

  future: {
    v4: true,
  },

  url: 'https://speca.pages.dev',
  baseUrl: '/',

  organizationName: 'NyxFoundation',
  projectName: 'speca',

  onBrokenLinks: 'throw',

  i18n: {
    defaultLocale: 'ja',
    locales: ['ja', 'en'],
    localeConfigs: {
      ja: {label: '日本語'},
      en: {label: 'English'},
    },
  },

  presets: [
    [
      'classic',
      /** @type {import('@docusaurus/preset-classic').Options} */
      ({
        docs: {
          sidebarPath: './sidebars.js',
          editUrl:
            'https://github.com/NyxFoundation/speca/tree/dev/website/',
        },
        blog: {
          showReadingTime: true,
          feedOptions: {
            type: ['rss', 'atom'],
            xslt: true,
          },
          editUrl:
            'https://github.com/NyxFoundation/speca/tree/dev/website/',
          onInlineTags: 'warn',
          onInlineAuthors: 'warn',
          onUntruncatedBlogPosts: 'warn',
        },
        theme: {
          customCss: './src/css/custom.css',
        },
      }),
    ],
  ],

  themeConfig:
    /** @type {import('@docusaurus/preset-classic').ThemeConfig} */
    ({
      image: 'img/speca_logo.svg',
      colorMode: {
        respectPrefersColorScheme: true,
      },
      navbar: {
        title: 'SPECA',
        logo: {
          alt: 'SPECA logo',
          src: 'img/speca_logo.svg',
        },
        items: [
          {
            type: 'docSidebar',
            sidebarId: 'tutorialSidebar',
            position: 'left',
            label: 'ドキュメント',
          },
          {to: '/blog', label: 'ブログ', position: 'left'},
          {
            type: 'localeDropdown',
            position: 'right',
          },
          {
            href: 'https://github.com/NyxFoundation/speca',
            label: 'GitHub',
            position: 'right',
          },
        ],
      },
      footer: {
        style: 'light',
        logo: {
          alt: 'Nyx Foundation',
          src: 'img/nyx_foundation.png',
          href: 'https://nyx.foundation/',
          width: 200,
        },
        links: [
          {
            title: 'ドキュメント',
            items: [
              {label: 'はじめる', to: '/docs/intro'},
            ],
          },
          {
            title: 'プロジェクト',
            items: [
              {label: 'GitHub', href: 'https://github.com/NyxFoundation/speca'},
              {label: 'Issues', href: 'https://github.com/NyxFoundation/speca/issues'},
              {label: 'リリース', href: 'https://github.com/NyxFoundation/speca/releases'},
            ],
          },
          {
            title: 'Nyx Foundation',
            items: [
              {label: 'nyx.foundation', href: 'https://nyx.foundation/'},
            ],
          },
        ],
        copyright: `© ${new Date().getFullYear()} Nyx Foundation. SPECA は MIT License で公開されています。`,
      },
      prism: {
        theme: prismThemes.github,
        darkTheme: prismThemes.dracula,
      },
    }),
};

export default config;
