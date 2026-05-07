// @ts-check
import {themes as prismThemes} from 'prism-react-renderer';

/** @type {import('@docusaurus/types').Config} */
const config = {
  title: 'SPECA',
  tagline: 'Specification-to-Property Agentic Auditing',
  favicon: 'img/speca_logo.png',

  future: {
    v4: true,
  },

  url: 'https://nyx.foundation',
  baseUrl: '/speca/',

  organizationName: 'NyxFoundation',
  projectName: 'speca',

  onBrokenLinks: 'throw',

  i18n: {
    defaultLocale: 'en',
    locales: ['en'],
  },

  presets: [
    [
      'classic',
      /** @type {import('@docusaurus/preset-classic').Options} */
      ({
        docs: {
          sidebarPath: './sidebars.js',
          editUrl:
            'https://github.com/NyxFoundation/speca/tree/dev/homepage/',
        },
        blog: {
          showReadingTime: true,
          feedOptions: {
            type: ['rss', 'atom'],
            xslt: true,
          },
          editUrl:
            'https://github.com/NyxFoundation/speca/tree/dev/homepage/',
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
      image: 'img/speca_logo.png',
      colorMode: {
        respectPrefersColorScheme: true,
      },
      navbar: {
        title: 'SPECA',
        logo: {
          alt: 'SPECA logo',
          src: 'img/speca_logo.png',
        },
        items: [
          {
            type: 'docSidebar',
            sidebarId: 'tutorialSidebar',
            position: 'left',
            label: 'Docs',
          },
          {to: '/blog', label: 'Blog', position: 'left'},
          {
            href: 'https://github.com/NyxFoundation/speca',
            label: 'GitHub',
            position: 'right',
          },
        ],
      },
      footer: {
        style: 'light',
        links: [
          {
            title: 'Docs',
            items: [
              {label: 'Get started', to: '/docs/intro'},
            ],
          },
          {
            title: 'Project',
            items: [
              {label: 'GitHub', href: 'https://github.com/NyxFoundation/speca'},
              {label: 'Issues', href: 'https://github.com/NyxFoundation/speca/issues'},
              {label: 'Releases', href: 'https://github.com/NyxFoundation/speca/releases'},
            ],
          },
          {
            title: 'Nyx Foundation',
            items: [
              {label: 'nyx.foundation', href: 'https://nyx.foundation/'},
            ],
          },
        ],
        copyright: `© ${new Date().getFullYear()} Nyx Foundation. SPECA is released under the Apache License 2.0.`,
      },
      prism: {
        theme: prismThemes.github,
        darkTheme: prismThemes.dracula,
      },
    }),
};

export default config;
