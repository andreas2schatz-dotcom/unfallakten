function reducer(state, action) {
  const { akteId } = action;
  const cur = state[akteId] || {};
  switch (action.type) {
    case "SAVE_BETEILIGTER": {
      const list = cur.beteiligte || [];
      const idx  = list.findIndex(b => b.id === action.beteiligter.id);
      return { ...state, [akteId]:{ ...cur, beteiligte: idx>=0 ? list.map((b,i) => i===idx ? action.beteiligter : b) : [...list, action.beteiligter] } };
    }
    case "DELETE_BETEILIGTER":
      return { ...state, [akteId]:{ ...cur, beteiligte:(cur.beteiligte||[]).filter(b => b.id!==action.id) } };
    case "SET_BETEILIGTE":
      return { ...state, [akteId]:{ ...cur, beteiligte: action.beteiligte } };
    case "SAVE_SCHADEN":
      return { ...state, [akteId]:{ ...cur, schaden:action.schaden } };
    case "SET_ABRECHNUNGEN":
      return { ...state, [akteId]:{ ...cur, abrechnungen: action.abrechnungen } };
    case "ADD_ABRECHNUNG":
      return { ...state, [akteId]:{ ...cur,
        abrechnungen: [action.abrechnung, ...(cur.abrechnungen || [])],
        regulierungen: [action.regulierung, ...(cur.regulierungen || [])],
      }};
    case "UPDATE_ABRECHNUNG":
      return { ...state, [akteId]:{ ...cur,
        abrechnungen: (cur.abrechnungen || []).map(a =>
          a.id === action.abrechnung.id ? action.abrechnung : a
        ),
      }};
    case "DELETE_ABRECHNUNG":
      return { ...state, [akteId]:{ ...cur,
        abrechnungen: (cur.abrechnungen || []).filter(a => a.id !== action.ab_id),
      }};
    case "SET_REGULIERUNGEN":
      return { ...state, [akteId]:{ ...cur, regulierungen: action.regulierungen } };
    case "ADD_REGULIERUNG":
      return { ...state, [akteId]:{ ...cur, regulierungen:[...(cur.regulierungen||[]), action.regulierung] } };
    case "ADD_DOKUMENT":
      return { ...state, [akteId]:{ ...cur, dokumente:[...(cur.dokumente||[]), action.dokument] } };
    case "SET_DOKUMENTE":
      return { ...state, [akteId]:{ ...cur, dokumente: action.dokumente } };
    case "DELETE_DOKUMENT":
      return { ...state, [akteId]:{ ...cur, dokumente:(cur.dokumente||[]).filter(d => String(d.id) !== String(action.id)) } };
    case "UPDATE_DOKUMENT_KLASSE":
      return { ...state, [akteId]:{ ...cur, dokumente:(cur.dokumente||[]).map(d => String(d.id)===String(action.dokId) ? { ...d, dokumentenklasse:action.dokumentenklasse, parse_status:action.parse_status } : d) } };
    case "SET_AKTIVITAETEN":
      return { ...state, [akteId]:{ ...cur, aktivitaeten: action.aktivitaeten } };
    case "PREPEND_AKTIVITAET":
      return { ...state, [akteId]:{ ...cur, aktivitaeten: [action.aktivitaet, ...(cur.aktivitaeten||[])] } };
    case "SET_STATUS":
      return { ...state, [akteId]:{ ...cur, status:action.status } };
    case "SET_NOTIZEN":
      return { ...state, [akteId]:{ ...cur, notizen:action.notizen } };
    case "SET_BELEGE_KANDIDATEN":
      return { ...state, [akteId]:{ ...cur, belegeKandidaten: action.kandidaten } };
    default: return state;
  }
}



export default reducer;
