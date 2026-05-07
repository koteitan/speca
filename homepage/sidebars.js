// @ts-check

// This runs in Node.js - Don't use client-side code here (browser APIs, JSX...)

/**
 * Creating a sidebar enables you to:
 - create an ordered group of docs
 - render a sidebar for each doc of that group
 - provide next/previous navigation

 The sidebars can be generated from the filesystem, or explicitly defined here.

 Create as many sidebars as you want.

 @type {import('@docusaurus/plugin-content-docs').SidebarsConfig}
 */
const sidebars = {
  tutorialSidebar: [
    'intro',
    {
      type: 'category',
      label: 'はじめに',
      collapsed: false,
      items: ['getting-started/installation', 'getting-started/quickstart'],
    },
    {
      type: 'category',
      label: 'パイプライン',
      collapsed: false,
      items: [
        'pipeline/overview',
        'pipeline/01a-spec-discovery',
        'pipeline/01b-subgraph-extraction',
        'pipeline/01e-property-generation',
        'pipeline/02c-code-resolution',
        'pipeline/audit-map',
        'pipeline/review',
      ],
    },
    {
      type: 'category',
      label: '概念',
      collapsed: true,
      items: [
        'concepts/spec-driven',
        'concepts/proof-attempt',
        'concepts/gate-review',
        'concepts/bug-bounty-scope',
      ],
    },
  ],
};

export default sidebars;
