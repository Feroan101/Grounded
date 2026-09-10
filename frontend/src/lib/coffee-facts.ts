export const COFFEE_FACTS = [
  {
    title: "The Origin of Coffee",
    fact: "Coffee was first discovered in Ethiopia around the 9th century. According to legend, a goatherd named Kaldi noticed his goats dancing energetically after eating berries from a certain bush.",
  },
  {
    title: "Espresso Timing",
    fact: "A standard espresso shot is extracted in exactly 25 to 30 seconds. Too fast and it tastes sour; too slow and it turns bitter. The sweet spot is where the magic happens.",
  },
  {
    title: "Coffee Bean Varieties",
    fact: "There are over 100 species of coffee, but only two dominate global production: Arabica (known for smooth, complex flavor) and Robusta (higher caffeine, bolder taste).",
  },
  {
    title: "The Maillard Reaction",
    fact: "The rich, complex flavors in roasted coffee come from the Maillard reaction\u2014the same chemical process that browns bread crust and seared steak.",
  },
  {
    title: "World\u2019s Most Expensive Coffee",
    fact: "Kopi Luwak is one of the world\u2019s priciest coffees. The beans are digested and excreted by the Asian palm civet, which is believed to enhance the flavor.",
  },
  {
    title: "Finland\u2019s Coffee Love",
    fact: "Finns consume more coffee per capita than any other nation\u2014roughly 12 kilograms per person per year, or about four cups a day.",
  },
  {
    title: "Cold Brew Takes Time",
    fact: "Cold brew coffee steeps for 12 to 24 hours, compared to a few minutes for hot brew. The result is a smoother, less acidic concentrate that\u2019s naturally sweet.",
  },
  {
    title: "The Golden Ratio",
    fact: "The generally accepted golden ratio for brewing coffee is 1:15\u2014one gram of coffee for every 15 grams of water. Small adjustments here make a big difference in taste.",
  },
  {
    title: "Coffee and Antioxidants",
    fact: "Coffee is the single largest source of antioxidants in the modern Western diet, providing more polyphenols than most fruits or vegetables.",
  },
  {
    title: "The Perfect Water Temperature",
    fact: "The ideal water temperature for brewing coffee is between 195\u00b0F and 205\u00b0F (90\u00b0C\u201396\u00b0C). Boiling water can scorch the grounds and create bitterness.",
  },
  {
    title: "Caffeine and Sleep",
    fact: "Caffeine has a half-life of about 5 to 6 hours. That means half of the caffeine from your 3 PM latte is still in your system at 9 PM.",
  },
  {
    title: "The Espresso Crema",
    fact: "That golden-brown foam on top of an espresso is called crema. It\u2019s created by CO\u2082 gases trapped in coffee oils under high pressure, and it carries much of the aroma.",
  },
  {
    title: "Single Origin vs Blend",
    fact: "Single-origin coffee comes from one farm or region, showcasing unique terroir. Blends combine beans from multiple origins to create a balanced, consistent flavor profile.",
  },
  {
    title: "The Grind Matters",
    fact: "Grinding coffee right before brewing preserves volatile aromatics that begin to oxidize within minutes. Pre-ground coffee loses noticeable flavor within 15 minutes of opening.",
  },
  {
    title: "Americano History",
    fact: "The Americano was born during World War II when American soldiers in Italy found espresso too strong and diluted it with hot water to make it more familiar.",
  },
  {
    title: "Roast Levels",
    fact: "Light roasts retain more of the bean\u2019s original flavor and acidity. Dark roasts develop bolder, smokier notes from longer roasting. Neither has more caffeine by volume.",
  },
  {
    title: "Coffee\u2019s Journey to Europe",
    fact: "Coffee arrived in Europe in the 17th century and was initially met with suspicion. The Pope reportedly tasted it, gave his blessing, and it became wildly popular across the continent.",
  },
  {
    title: "Pour-Over Precision",
    fact: "A pour-over brew takes 3 to 4 minutes from start to finish. The key is a slow, consistent spiral pour that evenly saturates the grounds for balanced extraction.",
  },
  {
    title: "Decaf Isn\u2019t Caffeine-Free",
    fact: "Decaffeinated coffee still contains about 2 to 15 milligrams of caffeine per cup, compared to 80 to 100 milligrams in regular coffee.",
  },
  {
    title: "The Coffee Belt",
    fact: "Most of the world\u2019s coffee grows in the \u201ccoffee belt\u201d\u2014a band between the Tropics of Cancer and Capricorn where the climate is warm, rainy, and ideal for coffee cultivation.",
  },
  {
    title: "Turkish Coffee Tradition",
    fact: "In Turkish coffee culture, the grounds left in the cup are sometimes read for fortune-telling. UNESCO recognizes Turkish coffee as an Intangible Cultural Heritage.",
  },
  {
    title: "The Nitro Trend",
    fact: "Nitro cold brew is infused with nitrogen gas, giving it a creamy, stout-like texture and a naturally sweet taste\u2014all without any dairy or sweetener.",
  },
  {
    title: "Coffee\u2019s Peak Hours",
    fact: "Most people reach for coffee between 9:30 and 11:30 AM, when cortisol (the body\u2019s natural alertness hormone) begins to dip after its morning peak.",
  },
  {
    title: "The Flat White Origin",
    fact: "The flat white\u2014a velvety espresso-and-milk drink\u2014is claimed by both Australia and New Zealand. The friendly debate over its origin continues to this day.",
  },
  {
    title: "Washed vs Natural Process",
    fact: "In washed processing, the fruit is removed from the bean before drying, yielding a cleaner cup. Natural processing dries the whole cherry on the bean, creating bolder, fruitier flavors.",
  },
];

export function getRandomFact(excludeIndex?: number): { title: string; fact: string; index: number } {
  let index: number;
  do {
    index = Math.floor(Math.random() * COFFEE_FACTS.length);
  } while (index === excludeIndex && COFFEE_FACTS.length > 1);
  return { ...COFFEE_FACTS[index], index };
}
