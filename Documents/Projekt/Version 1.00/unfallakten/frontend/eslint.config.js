// eslint.config.js – Unfallakten Frontend
import js from "@eslint/js";
import reactPlugin from "eslint-plugin-react";
import reactHooks from "eslint-plugin-react-hooks";
import globals from "globals";

export default [
  js.configs.recommended,
  {
    files: ["src/**/*.{js,jsx}"],
    plugins: {
      react:        reactPlugin,
      "react-hooks": reactHooks,
    },
    languageOptions: {
      ecmaVersion: 2022,
      sourceType:  "module",
      globals: {
        ...globals.browser,
        ...globals.es2021,
      },
      parserOptions: {
        ecmaFeatures: { jsx: true },
      },
    },
    settings: {
      react: { version: "18" },
    },
    rules: {
      // React
      ...reactPlugin.configs.recommended.rules,
      ...reactHooks.configs.recommended.rules,
      "react/react-in-jsx-scope":  "off",   // nicht nötig in React 18
      "react/prop-types":          "off",   // kein TypeScript nötig
      "react/display-name":        "off",

      // Allgemein
      "no-unused-vars":   ["warn", { argsIgnorePattern: "^_", varsIgnorePattern: "^_" }],
      "no-console":       "off",
      "no-undef":         "error",
      "prefer-const":     "warn",
      "no-var":           "error",
    },
  },
  {
    // Ignoriere Build-Ausgabe und Node-Verzeichnis
    ignores: ["dist/**", "node_modules/**", "*.config.js"],
  },
];
