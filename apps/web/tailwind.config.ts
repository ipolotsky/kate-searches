import type { Config } from "tailwindcss";
import flowbiteReact from "flowbite-react/plugin/tailwindcss";

const config: Config = {
  content: ["./src/**/*.{js,ts,jsx,tsx,mdx}", ".flowbite-react/class-list.json"],
  darkMode: "class",
  theme: {
    extend: {},
  },
  plugins: [flowbiteReact],
};

export default config;
