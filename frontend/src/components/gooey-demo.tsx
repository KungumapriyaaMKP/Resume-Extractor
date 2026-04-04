import { useScreenSize } from "@/hooks/use-screen-size"
import { PixelTrail } from "@/components/ui/pixel-trail"
import { GooeyFilter } from "@/components/ui/gooey-filter"

function GooeyDemo({ children }: { children?: React.ReactNode }) {
  const screenSize = useScreenSize()

  return (
    <div className="relative w-full h-screen min-h-[600px] flex flex-col items-center justify-center gap-8 bg-black text-center text-pretty overflow-hidden">
      <img
        src="https://images.unsplash.com/photo-1497215728101-856f4ea42174?q=80&w=2000&auto=format&fit=crop"
        alt="professional workspace background"
        className="w-full h-full object-cover absolute inset-0 opacity-40 grayscale-[20%]"
      />

      <GooeyFilter id="gooey-filter-pixel-trail" strength={5} />

      <div
        className="absolute inset-0 z-0"
        style={{ filter: "url(#gooey-filter-pixel-trail)" }}
      >
        <PixelTrail
          pixelSize={screenSize.lessThan(`md`) ? 24 : 32}
          fadeDuration={0}
          delay={500}
          pixelClassName="bg-white"
        />
      </div>

      <div className="relative z-10 w-full px-4">
        {children}
      </div>
    </div>
  )
}

export { GooeyDemo }
