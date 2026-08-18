using Avalonia;
using Avalonia.Controls;
using Avalonia.Rendering.Composition;
using AristeusUI.Enums;
using AristeusUI.Utilities.Effects;

namespace AristeusUI.Controls
{
    public class AristeusBackground : Control
    {
        public static readonly StyledProperty<AristeusBackgroundStyle> StyleProperty =
            AvaloniaProperty.Register<AristeusBackground, AristeusBackgroundStyle>(nameof(Style),
                defaultValue: AristeusBackgroundStyle.Gradient);

        /// <summary>
        /// Which of the default background styles to use - DEFAULT: Gradient
        /// </summary>
        public AristeusBackgroundStyle Style
        {
            get => GetValue(StyleProperty);
            set => SetValue(StyleProperty, value);
        }

        public static readonly StyledProperty<string?> ShaderFileProperty =
            AvaloniaProperty.Register<AristeusBackground, string?>(nameof(ShaderFile));

        /// <summary>
        /// Specify a filename of an EMBEDDED RESOURCE file of type `.SkSL` with or without extension and it will be loaded and displayed.
        /// This takes priority over the <see cref="ShaderCode"/> property, which in turns takes priority over <see cref="Style"/>.
        /// </summary>
        public string? ShaderFile
        {
            get => GetValue(ShaderFileProperty);
            set => SetValue(ShaderFileProperty, value);
        }

        public static readonly StyledProperty<string?> ShaderCodeProperty =
            AvaloniaProperty.Register<AristeusBackground, string?>(nameof(ShaderCode));

        /// <summary>
        /// Specify the shader code to use directly, simpler if you don't want to create an .SkSL file or want to generate the shader effect at runtime in some way.
        /// This takes priority over the <see cref="Style"/> property, but is second in priority to <see cref="ShaderFile"/> if it is set.
        /// </summary>
        public string? ShaderCode
        {
            get => GetValue(ShaderCodeProperty);
            set => SetValue(ShaderCodeProperty, value);
        }

        public static readonly StyledProperty<bool> AnimationEnabledProperty =
            AvaloniaProperty.Register<AristeusBackground, bool>(nameof(AnimationEnabled), defaultValue: false);

        /// <summary>
        /// [WARNING: This feature is experimental and has relatively high GPU utilisation] Enables/disables animations - DEFAULT: False
        /// </summary>
        public bool AnimationEnabled
        {
            get => GetValue(AnimationEnabledProperty);
            set => SetValue(AnimationEnabledProperty, value);
        }

        public static readonly StyledProperty<bool> TransitionsEnabledProperty =
            AvaloniaProperty.Register<AristeusBackground, bool>(nameof(TransitionsEnabled), defaultValue: false);

         /// <summary>
        /// Enables/disables transition animations when switching backgrounds, Currently non-functional - DEFAULT: False
        /// </summary>
        public bool TransitionsEnabled
        {
            get => GetValue(TransitionsEnabledProperty);
            set => SetValue(TransitionsEnabledProperty, value);
        }

        public static readonly StyledProperty<double> TransitionTimeProperty =
            AvaloniaProperty.Register<AristeusBackground, double>(nameof(TransitionTime), defaultValue: 1.0);

        /// <summary>
        /// The amount of time in seconds the background transition will take - DEFAULT: 1.0
        /// </summary>
        public double TransitionTime
        {
            get => GetValue(TransitionTimeProperty);
            set => SetValue(TransitionTimeProperty, value);
        }

        public static readonly StyledProperty<bool> ForceSoftwareRenderingProperty = AvaloniaProperty.Register<AristeusBackground, bool>(nameof(ForceSoftwareRendering));

        public bool ForceSoftwareRendering
        {
            get => GetValue(ForceSoftwareRenderingProperty);
            set => SetValue(ForceSoftwareRenderingProperty, value);
        }

        private CompositionCustomVisual? _customVisual;

        public AristeusBackground()
        {
            IsHitTestVisible = false;
        }

        protected override void OnAttachedToVisualTree(VisualTreeAttachmentEventArgs e)
        {
            base.OnAttachedToVisualTree(e);
            var comp = ElementComposition.GetElementVisual(this)?.Compositor;
            if (comp == null || _customVisual?.Compositor == comp) return;
            var visualHandler = new EffectBackgroundDraw();
            _customVisual = comp.CreateCustomVisual(visualHandler);
            ElementComposition.SetElementChildVisual(this, _customVisual);
            _customVisual.SendHandlerMessage(TransitionTime);
            HandleBackgroundStyleChanges();
            Update();
        }

        private void Update()
        {
            if (_customVisual == null) return;
            _customVisual.Size = new Vector(Bounds.Width, Bounds.Height);
        }

        protected override void OnPropertyChanged(AvaloniaPropertyChangedEventArgs change)
        {
            base.OnPropertyChanged(change);
            if (change.Property == BoundsProperty)
                Update();
            else if (change.Property == ForceSoftwareRenderingProperty && change.NewValue is bool forceSoftwareRendering)
                _customVisual?.SendHandlerMessage(forceSoftwareRendering
                    ? EffectDrawBase.EnableForceSoftwareRendering
                    : EffectDrawBase.DisableForceSoftwareRendering);
            else if(change.Property == TransitionsEnabledProperty && change.NewValue is bool transitionEnabled)
                _customVisual?.SendHandlerMessage(transitionEnabled
                    ? EffectBackgroundDraw.EnableTransitions
                    : EffectBackgroundDraw.DisableTransitions);
            else if(change.Property == TransitionTimeProperty && change.NewValue is double transitionTime)
                _customVisual?.SendHandlerMessage(transitionTime);
            else if (change.Property == AnimationEnabledProperty && change.NewValue is bool animationEnabled)
                _customVisual?.SendHandlerMessage(animationEnabled
                    ? EffectDrawBase.StartAnimations
                    : EffectDrawBase.StopAnimations);
            else if(change.Property == StyleProperty || change.Property == ShaderFileProperty || change.Property == ShaderCodeProperty)
                HandleBackgroundStyleChanges();
        }

        private void HandleBackgroundStyleChanges()
        {
            AristeusEffect effect;
            if (ShaderFile is not null)
                effect = AristeusEffect.FromEmbeddedResource(ShaderFile);
            else if (ShaderCode is not null)
                effect = AristeusEffect.FromString(ShaderCode);
            else
                effect = AristeusEffect.FromEmbeddedResource(Style.ToString());
            _customVisual?.SendHandlerMessage(effect);
        }
    }
}