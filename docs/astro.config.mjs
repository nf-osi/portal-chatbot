// @ts-check
import { defineConfig } from 'astro/config';
import starlight from '@astrojs/starlight';

// https://astro.build/config
export default defineConfig({
	site: 'https://nf-osi.github.io',
	base: '/portal-chatbot',
	// src/content/docs is a symlink to the repo's top-level docs/ —
	// preserveSymlinks keeps module resolution anchored to site/ instead of
	// following the link to a real path outside node_modules' reach.
	vite: {
		resolve: {
			preserveSymlinks: true,
		},
	},
	integrations: [
		starlight({
			title: 'NF Portal Copilot Docs',
			social: [{ icon: 'github', label: 'GitHub', href: 'https://github.com/nf-osi/portal-chatbot' }],
			sidebar: [
				{
					label: 'Start Here',
					items: [
						{ label: 'So you want a portal copilot?', slug: 'so-you-want-a-portal-copilot' },
						{ label: 'Reference workflow', slug: 'nf-portal-agent-workflow' },
						{ label: 'Reusable pieces', slug: 'reusable-pieces' },
						{ label: 'Deployment', slug: 'deployment' },
					],
				},
				{
					label: 'Benchmarking and Evaluation',
					items: [
						{ label: 'Overview', slug: 'benchmarking-and-evaluation' },
						{ label: 'Grounded retrieval', slug: 'grounded-retrieval' },
						{ label: 'Source routing', slug: 'source-routing' },
						{ label: 'Red teaming', slug: 'red-teaming' },
					],
				},
			],
		}),
	],
});
