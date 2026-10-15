// Small formatting helpers shared by the Plan page and its cards, so a hall or meal can't read
// differently in two places.

export const fmt = (n) => (n == null ? '—' : Math.round(n))

// "Ikenberry Dining Center (Ike)" -> "Ike" for compact buttons; the full name is still what we send
export const shortHall = (hall) => hall.match(/\(([^)]+)\)\s*$/)?.[1] || hall

// "light lunch" -> "Light lunch"
export const mealLabel = (meal) => meal.charAt(0).toUpperCase() + meal.slice(1)
