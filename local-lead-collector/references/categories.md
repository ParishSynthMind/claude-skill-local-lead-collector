# Built-in categories

Use the name on the left with `--category`. Each one searches every OSM tag listed,
because mappers tag the same kind of business in different ways. Anything missing
can be searched directly with `--tag key=value` (see the OSM wiki page "Map features").

| Category | OSM tags searched | Also accepts |
|---|---|---|
| `dentist` | `amenity=dentist`, `healthcare=dentist` | dental, dental clinic, dental clinics, dentists |
| `doctor` | `amenity=doctors`, `healthcare=doctor` | doctors, gp |
| `clinic` | `amenity=clinic`, `healthcare=clinic` | clinics |
| `pharmacy` | `amenity=pharmacy`, `healthcare=pharmacy` | pharmacies |
| `veterinary` | `amenity=veterinary` | vet, vets |
| `physiotherapist` | `healthcare=physiotherapist` | physio |
| `restaurant` | `amenity=restaurant` | restaurants |
| `cafe` | `amenity=cafe` | cafes, coffee shop |
| `bar` | `amenity=bar`, `amenity=pub` | pubs |
| `hotel` | `tourism=hotel` | hotels |
| `gym` | `leisure=fitness_centre` | fitness, gyms |
| `hairdresser` | `shop=hairdresser` | hair salon, salon |
| `beauty` | `shop=beauty` | beauty salon |
| `bakery` | `shop=bakery` |  |
| `car_repair` | `shop=car_repair` | garage |
| `car_dealer` | `shop=car` |  |
| `estate_agent` | `office=estate_agent` | estate agents, real estate, real estate agent |
| `lawyer` | `office=lawyer` | law firm, lawyers |
| `accountant` | `office=accountant` | accountants, accounting |
| `insurance` | `office=insurance` |  |
| `it_company` | `office=it` | it, software company |
| `architect` | `office=architect` |  |
| `school` | `amenity=school` | schools |
| `kindergarten` | `amenity=kindergarten` | nursery |
| `driving_school` | `amenity=driving_school` |  |
| `florist` | `shop=florist` |  |
| `optician` | `shop=optician`, `healthcare=optometrist` | opticians |
| `electronics` | `shop=electronics` |  |
| `furniture` | `shop=furniture` |  |
| `supermarket` | `shop=supermarket` |  |

Combine several: `--category dentist --category clinic`.
Raw tag examples: `--tag shop=bicycle`, `--tag craft=carpenter`, `--tag office=company`.
