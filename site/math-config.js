window.MathJax = {
  loader: { load: ['ui/safe'] },
  tex: { inlineMath: [['$', '$'], ['\\(', '\\)']], displayMath: [['$$', '$$'], ['\\[', '\\]']], processEscapes: true },
  options: { enableMenu: false, safeOptions: { allow: { URLs: 'safe', classes: 'none', cssIDs: 'none', styles: 'none' } } },
  startup: { typeset: false, ready() { MathJax.startup.defaultReady(); document.dispatchEvent(new Event('math-ready')); } }
};
