composer.when(
    composer.action('authenticate'),
    composer.action('success'),
    composer.action('failure'))
