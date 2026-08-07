using Avalonia;
using Avalonia.Controls;
using Avalonia.Markup.Xaml;
using Avalonia.Threading;

namespace AristeusUI.Controls.GlassMorphism
{
    public partial class AristeusBlurBackground : UserControl
    {
        public static readonly StyledProperty<bool> IsDynamicProperty = AvaloniaProperty.Register<AristeusBlurBackground, bool>(
            nameof(IsDynamic), false);

        public bool IsDynamic
        {
            get => GetValue(IsDynamicProperty);
            set
            {
                SetValue(IsDynamicProperty, value);
                this.Get<BlurBackground>("BB").IsDynamic = value;  
            }
        }
        
        public static readonly StyledProperty<double> IntensityFactorProperty =
            AvaloniaProperty.Register<AristeusBlurBackground, double>(nameof(IntensityFactor), 1d);

        public double IntensityFactor
        {
            get => GetValue(IntensityFactorProperty);
            set
            {
                SetValue(IntensityFactorProperty, value);
                this.Get<BlurBackground>("BB").IntensityFactor = value;  
            }
        }
        
        public AristeusBlurBackground()
        {
            InitializeComponent();
        }
        
        
    }
}