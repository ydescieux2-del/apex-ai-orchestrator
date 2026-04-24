import AnimatedHeading from './components/AnimatedHeading';
import FadeIn from './components/FadeIn';

export default function App() {
  return (
    <div className="min-h-screen bg-black text-white relative">
      <video
        autoPlay
        loop
        muted
        playsInline
        className="absolute inset-0 w-full h-full object-cover"
      >
        <source
          src="https://d8j0ntlcm91z4.cloudfront.net/user_38xzZboKV_Jun_06_2025_22_12_47_GMT_0000_bg_video.mp4"
          type="video/mp4"
        />
      </video>

      <div className="relative z-10 min-h-screen">
        <nav className="absolute top-0 left-0 right-0 px-6 md:px-12 lg:px-16 pt-6">
          <div className="liquid-glass rounded-xl flex items-center justify-between px-4 py-2">
            <div className="text-2xl font-semibold tracking-tight">VEX</div>
            <div className="hidden md:flex gap-8 text-sm">
              <a href="#" className="hover:text-gray-300 transition-colors">
                Story
              </a>
              <a href="#" className="hover:text-gray-300 transition-colors">
                Investing
              </a>
              <a href="#" className="hover:text-gray-300 transition-colors">
                Building
              </a>
              <a href="#" className="hover:text-gray-300 transition-colors">
                Advisory
              </a>
            </div>
            <button className="bg-white text-black px-6 py-2 rounded-lg text-sm font-medium hover:bg-gray-100">
              Start a Chat
            </button>
          </div>
        </nav>

        <div className="min-h-screen px-6 md:px-12 lg:px-16 flex flex-col items-center justify-center text-center">
          <div className="w-full max-w-4xl flex flex-col items-center">
            <AnimatedHeading
              text={'Shaping tomorrow\nwith vision and action.'}
              className="text-4xl md:text-5xl lg:text-6xl xl:text-7xl font-normal mb-4"
              style={{ letterSpacing: '-0.04em' }}
              delay={200}
              charDelay={30}
            />
            <FadeIn delay={800} duration={1000}>
              <p className="text-base md:text-lg text-gray-300 mb-5">
                We back visionaries and craft ventures that define what comes next.
              </p>
            </FadeIn>
            <FadeIn delay={1200} duration={1000}>
              <div className="flex flex-wrap gap-4 justify-center">
                <button className="bg-white text-black px-8 py-3 rounded-lg font-medium hover:bg-gray-100 transition-colors">
                  Start a Chat
                </button>
                <button className="liquid-glass border border-white/20 text-white px-8 py-3 rounded-lg font-medium hover:bg-white hover:text-black transition-colors">
                  Explore Now
                </button>
              </div>
            </FadeIn>
          </div>
        </div>

        <div className="absolute bottom-0 left-0 right-0 px-6 md:px-12 lg:px-16 pb-12 lg:pb-16 flex justify-center">
          <FadeIn delay={1400} duration={1000}>
            <div className="liquid-glass border border-white/20 px-6 py-3 rounded-xl">
              <p className="text-lg md:text-xl lg:text-2xl font-light">
                Investing. Building. Advisory.
              </p>
            </div>
          </FadeIn>
        </div>
      </div>
    </div>
  );
}
