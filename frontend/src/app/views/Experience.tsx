import { ArrowLeft, ArrowRight } from "lucide-react";
import { Link } from "react-router";
import {
  ButtonLink,
  Eyebrow,
  GoldSpecks,
  MenuItem,
  ReadMoreLink,
  SectionHeading,
} from "../design-system/primitives";
import { IMG } from "../design-system/assets";

export function Experience() {
  return (
    <>
      {/* Breadcrumb / back */}
      <div className="pt-28 md:pt-32 px-6 md:px-12 max-w-[1500px] mx-auto">
        <Link
          to="/"
          className="inline-flex items-center group text-[0.65rem] tracking-[0.2em] uppercase font-medium text-muted-foreground hover:text-primary transition-colors"
        >
          <ArrowLeft className="w-3 h-3 mr-2 group-hover:-translate-x-1 transition-transform" />
          Back to VenueFlow
        </Link>
      </div>

      {/* Hero */}
      <section className="relative w-full pt-16 pb-24 lg:pt-24 lg:pb-40">
        <div className="absolute top-0 left-0 w-full lg:w-[45%] h-[85%] bg-muted -z-10" />

        <div className="max-w-[1500px] mx-auto px-6 lg:px-12 grid grid-cols-1 lg:grid-cols-12 gap-16 lg:gap-0 relative">
          <div className="col-span-1 lg:col-span-5 flex flex-col justify-center lg:pr-16 xl:pr-24 z-10 pt-10 lg:pt-0">
            <Eyebrow text="Meet Our Expert" />
            <h1 className="font-serif text-5xl md:text-6xl lg:text-[5rem] leading-[1.1] mb-8 font-light">
              Event <span className="italic">True Master</span>
            </h1>
            <p className="text-muted-foreground leading-relaxed font-light mb-8 text-sm md:text-base max-w-md">
              The experience extends beyond planning — a curated atelier of catering,
              showrooms, and design expertise crafted for couples who notice the details.
            </p>
            <p className="text-muted-foreground leading-relaxed font-light mb-12 text-sm md:text-base max-w-md">
              Begin with a conversation. We'll meet you wherever your vision takes us.
            </p>
            <ReadMoreLink text="Discover More" to="/#contact" />
          </div>

          <div className="col-span-1 lg:col-span-7 relative">
            <div className="absolute -left-16 lg:-left-32 top-1/4 text-[20rem] lg:text-[30rem] font-serif text-primary opacity-15 -z-10 select-none pointer-events-none leading-none">
              W
            </div>
            <div className="aspect-[3/4] lg:aspect-[4/3] w-full overflow-hidden">
              <img
                src={IMG.brideBouquet}
                alt="Bride holding bouquet"
                className="w-full h-full object-cover object-top hover:scale-105 transition-transform duration-[1500ms]"
              />
            </div>
            {/* Bouquet inset — shared with Landing's True Master teaser */}
            <div className="absolute -bottom-12 -left-6 md:-bottom-16 md:-left-12 w-40 md:w-52 aspect-[3/4] overflow-hidden border-[8px] border-background bg-background shadow-2xl">
              <img src={IMG.bouquet} alt="Bride holding bouquet" className="w-full h-full object-cover" />
            </div>
            <GoldSpecks className="-top-6 -right-6 hidden md:block" />
          </div>
        </div>
      </section>

      {/* Social events */}
      <section className="py-24 lg:py-40">
        <div className="max-w-[1500px] mx-auto px-6 lg:px-12 grid grid-cols-1 lg:grid-cols-12 gap-16 lg:gap-24 items-center">
          <div className="col-span-1 lg:col-span-7 relative">
            <div className="w-[85%] aspect-[4/3] overflow-hidden">
              <img src={IMG.socialGathering} alt="Outdoor elegant gathering" className="w-full h-full object-cover" />
            </div>
            <div className="absolute bottom-[-15%] right-0 w-[45%] aspect-square border-[8px] border-background overflow-hidden bg-background">
              <img src={IMG.fineDining} alt="Fine dining table" className="w-full h-full object-cover" />
            </div>
          </div>

          <div className="col-span-1 lg:col-span-5 flex flex-col justify-center lg:pl-12 pt-16 lg:pt-0">
            <SectionHeading
              subtitle="Catering"
              title=""
              italic="Social events"
              className="mb-8"
            />
            <p className="text-muted-foreground leading-relaxed font-light mb-12 text-sm md:text-base max-w-md">
              Anniversaries, milestone birthdays, intimate dinners — every gathering
              receives the same considered hand. Fine details, warm service, quiet luxury.
            </p>
            <ReadMoreLink text="Read More" to="/#contact" />
          </div>
        </div>
      </section>

      {/* Menu */}
      <section className="py-24 lg:py-40 relative">
        <div className="max-w-[1500px] mx-auto px-6 lg:px-12 grid grid-cols-1 lg:grid-cols-12 gap-16 lg:gap-24 items-center">
          <div className="col-span-1 lg:col-span-5 flex flex-col justify-center lg:pr-12 order-2 lg:order-1">
            <SectionHeading
              subtitle="Elite Catering"
              title="Wedding"
              italic="vegan menu"
              className="mb-8"
            />
            <p className="text-muted-foreground leading-relaxed font-light mb-16 text-sm md:text-base max-w-md">
              Seasonal, plant-forward menus crafted in collaboration with our chef.
              A few signatures from this year's curation:
            </p>

            <div className="space-y-8 max-w-lg">
              <MenuItem
                title="Pulled jackfruit"
                description="radish, seeds, paprika, tomato, olive oil"
                price="$20"
              />
              <MenuItem
                title="Vegan meringues"
                description="chickpeas, sugar, soy cream, fruit"
                price="$15"
              />
              <MenuItem
                title="Wedding wreath"
                description="spinach, tofu, nutmeg, cherries"
                price="$35"
              />
            </div>
          </div>

          <div className="col-span-1 lg:col-span-7 relative flex justify-end order-1 lg:order-2 mb-16 lg:mb-0">
            <div className="w-[85%] aspect-[4/3] overflow-hidden">
              <img src={IMG.cocktail} alt="Woman holding cocktail" className="w-full h-full object-cover" />
            </div>
            <div className="absolute bottom-[-15%] left-0 w-[45%] aspect-square border-[8px] border-background overflow-hidden bg-background z-10">
              <img src={IMG.bottles} alt="Botanical bottles" className="w-full h-full object-cover" />
            </div>
          </div>
        </div>
      </section>

      {/* Weddings */}
      <section className="py-24 lg:py-40">
        <div className="max-w-[1500px] mx-auto px-6 lg:px-12 grid grid-cols-1 lg:grid-cols-12 gap-16 lg:gap-24 items-center">
          <div className="col-span-1 lg:col-span-7 relative">
            <div className="w-[85%] aspect-[4/3] overflow-hidden">
              <img src={IMG.weddingConfetti} alt="Wedding couple confetti" className="w-full h-full object-cover" />
            </div>
            <div className="absolute bottom-[-15%] right-0 w-[45%] aspect-[3/4] border-[8px] border-background overflow-hidden bg-background">
              <img src={IMG.champagne} alt="Champagne pour" className="w-full h-full object-cover" />
            </div>
          </div>

          <div className="col-span-1 lg:col-span-5 flex flex-col justify-center lg:pl-12 pt-16 lg:pt-0">
            <SectionHeading
              subtitle="Catering"
              title=""
              italic="Weddings"
              className="mb-8"
            />
            <p className="text-muted-foreground leading-relaxed font-light mb-12 text-sm md:text-base max-w-md">
              The centerpiece of our craft. From welcome drinks to the final toast,
              we choreograph every chapter with intention.
            </p>
            <ReadMoreLink text="Read More" to="/#contact" />
          </div>
        </div>
      </section>

      {/* Showroom */}
      <section className="py-32 relative overflow-hidden">
        <div className="absolute top-0 left-0 w-[45%] h-full bg-muted -z-10 hidden lg:block" />
        <div className="absolute top-0 left-0 w-full h-[60%] bg-muted -z-10 lg:hidden" />

        <div className="max-w-[1500px] mx-auto px-6 lg:px-12 flex justify-between items-end mb-16 relative z-10">
          <SectionHeading
            subtitle="Refined Style"
            title="Our Showroom"
            italic="in Carlow"
          />
          <div className="hidden md:flex space-x-4 pb-4">
            <button className="w-12 h-12 border border-border rounded-full flex items-center justify-center hover:bg-foreground hover:text-background transition-colors">
              <ArrowLeft className="w-4 h-4" />
            </button>
            <button className="w-12 h-12 border border-border rounded-full flex items-center justify-center hover:bg-foreground hover:text-background transition-colors">
              <ArrowRight className="w-4 h-4" />
            </button>
          </div>
        </div>

        <div className="w-full flex items-center justify-center relative h-[400px] sm:h-[500px] lg:h-[600px] max-w-[1920px] mx-auto">
          <div className="hidden md:block absolute left-[-10%] w-[30%] h-[70%] opacity-50 overflow-hidden">
            <img src={IMG.showroomLeft} alt="Interior detail" className="w-full h-full object-cover" />
          </div>

          <div className="w-[85%] md:w-[50%] h-full z-10 overflow-hidden shadow-2xl relative">
            <img src={IMG.showroom} alt="Showroom interior" className="w-full h-full object-cover" />
            <div className="absolute bottom-6 left-1/2 -translate-x-1/2 bg-background px-6 py-3 flex items-center space-x-4 border border-border">
              <span className="text-[0.65rem] tracking-[0.2em] uppercase font-medium">Homes</span>
              <ArrowRight className="w-3 h-3" />
            </div>
          </div>

          <div className="hidden md:block absolute right-[-10%] w-[30%] h-[70%] opacity-50 overflow-hidden">
            <img src={IMG.showroomRight} alt="Plant detail" className="w-full h-full object-cover" />
          </div>
        </div>
      </section>

      {/* Founder */}
      <section className="py-24 lg:py-40">
        <div className="max-w-[1500px] mx-auto px-6 lg:px-12 grid grid-cols-1 lg:grid-cols-12 gap-16 lg:gap-24 items-center">
          <div className="col-span-1 lg:col-span-5 flex flex-col justify-center lg:pr-12">
            <SectionHeading
              subtitle="Meet Our Expert"
              title="Event"
              italic="True Master"
              className="mb-8"
            />
            <p className="text-muted-foreground leading-relaxed font-light mb-6 text-sm md:text-base">
              For more than fifteen years, our founder has been quietly shaping some of
              the most refined weddings in the region — guided always by restraint, warmth,
              and an obsession with detail.
            </p>
            <p className="text-muted-foreground leading-relaxed font-light mb-12 text-sm md:text-base">
              The signature below is her promise: every event treated as the only one.
            </p>
            <div
              className="text-4xl md:text-5xl text-foreground opacity-80 pl-4"
              style={{ fontFamily: "'Great Vibes', cursive" }}
            >
              C. Truemaster
            </div>
          </div>

          <div className="col-span-1 lg:col-span-7 relative">
            <div className="w-full aspect-[4/5] md:aspect-[4/3] lg:aspect-[3/4] overflow-hidden max-w-[600px] ml-auto">
              <img src={IMG.founderPortrait} alt="Founder portrait" className="w-full h-full object-cover" />
            </div>
            {/* Aisle-at-night inset — shared with Landing's "passion" + gallery */}
            <div className="absolute -bottom-12 left-0 md:-bottom-16 md:left-4 w-40 md:w-48 aspect-[3/4] overflow-hidden border-[8px] border-background bg-background shadow-2xl">
              <img src={IMG.rusticReception} alt="Curated reception detail" className="w-full h-full object-cover" />
            </div>
            <GoldSpecks className="-top-4 right-8 hidden md:block" />
          </div>
        </div>
      </section>

      {/* Contact */}
      <section className="py-24 lg:py-32 bg-muted/50">
        <div className="max-w-[1500px] mx-auto px-6 lg:px-12 grid grid-cols-1 lg:grid-cols-2 gap-16 items-center">
          <div className="relative aspect-square md:aspect-[4/3] lg:aspect-[3/4] overflow-hidden">
            <img src={IMG.stationery} alt="Elegant stationery" className="w-full h-full object-cover" />
            {/* Long-catering inset — shared with Landing's contact section */}
            <div className="absolute -bottom-8 -right-6 md:-bottom-12 md:-right-10 w-44 md:w-56 aspect-[4/3] overflow-hidden border-[8px] border-background bg-background shadow-2xl">
              <img src={IMG.groomBride} alt="Groom and bride portrait" className="w-full h-full object-cover" />
            </div>
          </div>

          <div className="flex flex-col justify-center lg:pl-16">
            <SectionHeading
              subtitle="Get in Touch"
              title="Plan your"
              italic="dream event"
              className="mb-12"
            />

            <form className="space-y-8 max-w-lg">
              <div className="grid grid-cols-1 md:grid-cols-2 gap-8">
                <input
                  type="text"
                  placeholder="Your Name"
                  className="w-full border-b border-border bg-transparent pb-3 text-sm focus:outline-none focus:border-foreground transition-colors placeholder:text-muted-foreground/70"
                />
                <input
                  type="email"
                  placeholder="Email Address"
                  className="w-full border-b border-border bg-transparent pb-3 text-sm focus:outline-none focus:border-foreground transition-colors placeholder:text-muted-foreground/70"
                />
              </div>
              <input
                type="text"
                placeholder="Event Type & Date"
                className="w-full border-b border-border bg-transparent pb-3 text-sm focus:outline-none focus:border-foreground transition-colors placeholder:text-muted-foreground/70"
              />
              <textarea
                placeholder="Tell us about your vision..."
                rows={4}
                className="w-full border-b border-border bg-transparent pb-3 text-sm focus:outline-none focus:border-foreground transition-colors resize-none placeholder:text-muted-foreground/70"
              />
              <ButtonLink to="/#contact" variant="outline" className="mt-4">
                Send Inquiry
              </ButtonLink>
            </form>
          </div>
        </div>
      </section>
    </>
  );
}
