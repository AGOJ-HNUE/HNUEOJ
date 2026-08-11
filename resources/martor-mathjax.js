jQuery(function ($) {
    $(document).on('martor:preview', function (e, $content) {
        function update_math() {
            if (typeof window.renderMathJax === 'function') {
                window.renderMathJax($content[0]);
            } else if (window.MathJax && typeof window.MathJax.typesetPromise === 'function') {
                window.MathJax.typesetPromise([$content[0]]).then(function () {
                    $content.find('.tex-image').hide();
                    $content.find('.tex-text').show();
                }).catch(function () {});
            } else if (window.MathJax && window.MathJax.startup && window.MathJax.startup.promise) {
                window.MathJax.startup.promise.then(function () {
                    if (typeof window.MathJax.typesetPromise === 'function') {
                        return window.MathJax.typesetPromise([$content[0]]);
                    }
                }).then(function () {
                    $content.find('.tex-image').hide();
                    $content.find('.tex-text').show();
                }).catch(function () {});
            }
        }

        var $jax = $content.find('.require-mathjax-support');
        if ($jax.length) {
            var mathJaxReady = window.MathJax && (typeof window.MathJax.typesetPromise === 'function' || (window.MathJax.Hub && typeof window.MathJax.Hub.Queue === 'function'));
            var mathJaxLoading = window.MathJax && window.MathJax.startup && window.MathJax.startup.promise;

            if (!mathJaxReady && !mathJaxLoading) {
                var configUrl = $jax.attr('data-config') || '/static/mathjax_config.js';
                $.ajax({
                    type: 'GET',
                    url: configUrl,
                    dataType: 'script',
                    cache: true,
                    success: function () {
                        if (!window.MathJax || typeof window.MathJax.typesetPromise !== 'function') {
                            window.MathJax = window.MathJax || {};
                            window.MathJax.startup = window.MathJax.startup || {};
                            window.MathJax.startup.typeset = false;
                            $.ajax({
                                type: 'GET',
                                url: '/static/vnoj/mathjax/3.2.0/es5/tex-chtml.min.js',
                                dataType: 'script',
                                cache: true,
                                success: update_math
                            });
                        } else {
                            update_math();
                        }
                    }
                });
            } else {
                update_math();
            }
        }
    });
});
