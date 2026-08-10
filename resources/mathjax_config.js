window.MathJax = {
    loader: {
        load: ['[tex]/color'],
        paths: {
            mathjax: '/static/vnoj/mathjax/3.2.0/es5'
        }
    },
    tex: {
        packages: {
            '[+]': ['color']
        },
        inlineMath: [
            ['~', '~'],
            ['\\(', '\\)']
        ]
    },
    options: {
        enableMenu: false
    },
    startup: {
        pageReady: function () {
            return MathJax.startup.defaultPageReady().then(function () {
                if (window.jQuery) {
                    $('.tex-image').hide();
                    $('.tex-text').show();
                }
            });
        }
    }
};

window.renderMathJax = function (elements) {
    if (!window.MathJax) return;
    var targets = elements ? (Array.isArray(elements) ? elements : [elements]) : null;
    if (typeof window.MathJax.typesetPromise === 'function') {
        window.MathJax.typesetPromise(targets).then(function () {
            if (window.jQuery) {
                var $ctx = targets ? $(targets) : $(document);
                $ctx.find('.tex-image').hide();
                $ctx.find('.tex-text').show();
            }
        }).catch(function (err) {
            console.warn('MathJax typesetting error:', err);
        });
    } else if (window.MathJax.startup && window.MathJax.startup.promise) {
        window.MathJax.startup.promise.then(function () {
            if (typeof window.MathJax.typesetPromise === 'function') {
                return window.MathJax.typesetPromise(targets);
            }
        }).then(function () {
            if (window.jQuery) {
                var $ctx = targets ? $(targets) : $(document);
                $ctx.find('.tex-image').hide();
                $ctx.find('.tex-text').show();
            }
        }).catch(function () {});
    } else if (window.MathJax.Hub && typeof window.MathJax.Hub.Queue === 'function') {
        var queueArgs = ["Typeset", window.MathJax.Hub];
        if (targets && targets.length) {
            queueArgs.push(targets[0]);
        }
        window.MathJax.Hub.Queue(queueArgs, function () {
            if (window.jQuery) {
                var $ctx = targets ? $(targets) : $(document);
                $ctx.find('.tex-image').hide();
                $ctx.find('.tex-text').show();
            }
        });
    }
};
