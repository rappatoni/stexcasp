from __future__ import annotations

import html
import json
import urllib.parse
from collections.abc import Iterable, Mapping

from .graph import PrunedGraph, shortest_depths


def _label(uri: str) -> str:
    query = urllib.parse.parse_qs(urllib.parse.urlsplit(uri).query)
    return query.get("s", query.get("m", [uri]))[0]


def _archive(uri: str) -> str:
    query = urllib.parse.parse_qs(urllib.parse.urlsplit(uri).query)
    return query.get("a", [""])[0]


def render_html(
    graph: PrunedGraph,
    *,
    title: str | None = None,
    definitions: Mapping[str, Iterable[str]] | None = None,
) -> str:
    depths = shortest_depths(graph.root, graph.edges)
    definitions = definitions or {}
    nodes = [
        {
            "id": uri,
            "label": _label(uri),
            "archive": _archive(uri),
            "depth": depths.get(uri),
            "definitions": sorted(set(definitions.get(uri, ()))),
        }
        for uri in sorted(graph.nodes)
    ]
    links = [
        {"source": source, "target": target}
        for source, target in sorted(graph.edges)
    ]
    data = json.dumps(
        {
            "root": graph.root,
            "nodes": nodes,
            "links": links,
            "removed": len(graph.removed_back_edges),
        },
        ensure_ascii=False,
        separators=(",", ":"),
    ).replace("</", "<\\/")
    page_title = title or f"{_label(graph.root)} dependency graph"

    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{html.escape(page_title)}</title>
<script src="https://cdn.jsdelivr.net/npm/d3@7.9.0/dist/d3.min.js"></script>
<style>
:root {{ color-scheme: light dark; font-family: Inter, ui-sans-serif, system-ui, sans-serif; }}
* {{ box-sizing: border-box; }}
body {{ margin: 0; background: light-dark(#fafafa,#171717); color: light-dark(#171717,#f5f5f5); }}
main {{ min-height: 100vh; display: grid; grid-template-rows: auto auto 1fr auto; padding: 18px; gap: 10px; }}
header {{ display:flex; align-items:baseline; justify-content:space-between; gap:16px; flex-wrap:wrap; }}
h1 {{ margin:0; font-size:clamp(1.15rem,2.5vw,1.65rem); font-weight:600; }}
.stats,.hint {{ color:light-dark(#5b5b5b,#b8b8b8); font-size:.9rem; }}
.toolbar {{ display:flex; gap:12px; align-items:center; flex-wrap:wrap; }}
.toolbar label {{ font-size:.9rem; }}
input {{ min-width:min(340px,80vw); padding:7px 9px; border:1px solid light-dark(#c7c7c7,#555); border-radius:6px; background:light-dark(#fff,#242424); color:inherit; }}
.legend {{ display:flex; gap:14px; align-items:center; flex-wrap:wrap; font-size:.85rem; color:light-dark(#555,#c4c4c4); }}
.legend span {{ display:inline-flex; align-items:center; gap:5px; }}
.swatch {{ width:10px; height:10px; border-radius:50%; display:inline-block; }}
.root {{ background:#d83b3b; }} .direct {{ background:#e58a17; }} .transitive {{ background:#3683d6; }}
.workspace {{ min-width:0; display:grid; grid-template-columns:minmax(0,1fr) minmax(320px,38%); gap:10px; }}
#frame {{ position:relative; min-width:0; min-height:600px; overflow:hidden; border:1px solid light-dark(#d5d5d5,#444); border-radius:8px; background:light-dark(#fff,#1d1d1d); }}
svg {{ display:block; width:100%; height:100%; min-height:600px; touch-action:none; }}
.layer-line {{ stroke:light-dark(#d9d9d9,#3e3e3e); stroke-width:1; stroke-dasharray:4 6; vector-effect:non-scaling-stroke; }}
.layer-label {{ fill:light-dark(#777,#aaa); font-size:11px; text-anchor:end; }}
.edge {{ fill:none; stroke:light-dark(#777,#aaa); stroke-opacity:.3; stroke-width:1.1; }}
.edge.active {{ stroke:light-dark(#111,#fff); stroke-opacity:.9; stroke-width:1.8; }}
.edge.dim {{ stroke-opacity:.05; }}
.node circle {{ fill:#3683d6; stroke:light-dark(#fff,#1d1d1d); stroke-width:1.5; cursor:pointer; }}
.node[data-depth="0"] circle {{ fill:#d83b3b; }}
.node[data-depth="1"] circle {{ fill:#e58a17; }}
.node.dim {{ opacity:.15; }}
.node text {{ fill:light-dark(#171717,#f5f5f5); font-size:12px; pointer-events:none; paint-order:stroke; stroke:light-dark(#fff,#1d1d1d); stroke-width:3px; stroke-linejoin:round; }}
.tooltip {{ position:absolute; display:none; pointer-events:none; max-width:360px; padding:9px 11px; border:1px solid light-dark(#ccc,#555); border-radius:6px; background:light-dark(#fff,#282828); box-shadow:0 5px 18px #0003; font-size:.85rem; }}
.tooltip strong,.tooltip small {{ display:block; }}
.tooltip small {{ margin-top:3px; color:light-dark(#555,#bbb); overflow-wrap:anywhere; }}
#details {{ min-width:0; height:600px; overflow:auto; border:1px solid light-dark(#d5d5d5,#444); border-radius:8px; background:light-dark(#fff,#1d1d1d); padding:16px; }}
#details h2 {{ margin:0 0 4px; font-size:1.1rem; }}
#definition-uri {{ display:block; margin-bottom:12px; color:light-dark(#666,#aaa); font-size:.75rem; overflow-wrap:anywhere; }}
#definition-choice {{ width:100%; margin:0 0 12px; padding:6px; border:1px solid light-dark(#ccc,#555); border-radius:5px; background:inherit; color:inherit; }}
#definition-status {{ color:light-dark(#666,#aaa); font-size:.9rem; }}
#selection {{ min-height:1.5em; color:light-dark(#555,#bbb); font-size:.9rem; }}
@media (max-width:900px) {{ .workspace {{ grid-template-columns:1fr; }} #details {{ height:auto; max-height:600px; }} }}
@media (max-width:600px) {{ main {{ padding:10px; }} #frame,svg {{ min-height:680px; }} }}
</style>
</head>
<body>
<main>
  <header>
    <h1>{html.escape(page_title)}</h1>
    <div class="stats" id="stats"></div>
  </header>
  <div class="toolbar">
    <label for="search">Find concept</label>
    <input id="search" type="search" placeholder="Type a symbol name or URI">
    <div class="legend" aria-label="Legend">
      <span><i class="swatch root"></i>root</span>
      <span><i class="swatch direct"></i>direct</span>
      <span><i class="swatch transitive"></i>transitive</span>
    </div>
  </div>
  <div class="workspace">
    <div id="frame">
      <svg role="img" aria-labelledby="graph-title graph-desc">
        <title id="graph-title">{html.escape(page_title)}</title>
        <desc id="graph-desc">A directed acyclic graph layered by shortest-path distance from the root. Arrows point from defined concepts to referenced concepts. Drag nodes, zoom, search, or click a node to inspect its neighborhood and definition.</desc>
      </svg>
      <div class="tooltip" role="tooltip"></div>
    </div>
    <aside id="details" aria-live="polite">
      <h2 id="definition-title">Definition</h2>
      <code id="definition-uri"></code>
      <select id="definition-choice" aria-label="Definition paragraph" hidden></select>
      <div id="definition-status">Select a node to load its definition.</div>
      <div id="definition-body"></div>
    </aside>
  </div>
  <div id="selection" aria-live="polite">Click a node to highlight its dependencies and dependents.</div>
</main>
<script>
const DATA={data};
const frame=document.getElementById("frame");
const svg=d3.select("svg");
const tooltip=document.querySelector(".tooltip");
const selection=document.getElementById("selection");
const search=document.getElementById("search");
const definitionTitle=document.getElementById("definition-title");
const definitionUri=document.getElementById("definition-uri");
const definitionChoice=document.getElementById("definition-choice");
const definitionStatus=document.getElementById("definition-status");
const definitionBody=document.getElementById("definition-body");
const definitionShadow=definitionBody.attachShadow({{mode:"open"}});
const nodes=DATA.nodes.map(d=>({{...d}}));
const byId=new Map(nodes.map(d=>[d.id,d]));
const links=DATA.links.map(d=>({{source:byId.get(d.source),target:byId.get(d.target)}}));
const maxDepth=d3.max(nodes,d=>d.depth??0)??0;
let selected=null;
let linkSel,nodeSel,viewport;
let requestedDefinition=null;
const definitionCache=new Map();
const definitionCount=nodes.reduce((sum,node)=>sum+node.definitions.length,0);
document.getElementById("stats").textContent=DATA.nodes.length+" concepts · "+DATA.links.length+" edges · "+(maxDepth+1)+" levels · "+definitionCount+" definitions · "+DATA.removed+" back edges removed";

function clearDefinition(message){{
  requestedDefinition=null;
  definitionChoice.hidden=true;
  definitionChoice.replaceChildren();
  definitionStatus.textContent=message;
  definitionShadow.replaceChildren();
}}
function installDefinitionCss(css,root){{
  for(const entry of css??[]){{
    if(entry&&typeof entry.Link==="string"){{
      const link=document.createElement("link"); link.rel="stylesheet"; link.href=entry.Link; root.append(link);
    }}else if(entry&&typeof entry.Inline==="string"){{
      const style=document.createElement("style"); style.textContent=entry.Inline; root.append(style);
    }}
  }}
}}
function renderDefinition(payload){{
  definitionShadow.replaceChildren();
  const base=document.createElement("style");
  base.textContent=":host{{color:inherit}} .definition-fragment{{line-height:1.45}} .definition-fragment img{{max-width:100%}}";
  definitionShadow.append(base);
  installDefinitionCss(payload.css,definitionShadow);
  const content=document.createElement("div"); content.className="definition-fragment"; content.innerHTML=payload.html;
  definitionShadow.append(content);
}}
async function loadDefinition(node,uri){{
  const requestKey=node.id+"|"+uri;
  requestedDefinition=requestKey;
  definitionStatus.textContent="Loading definition…";
  definitionShadow.replaceChildren();
  try{{
    if(!definitionCache.has(uri)){{
      definitionCache.set(uri,fetch("/api/definition?"+new URLSearchParams({{uri}})).then(async response=>{{
        const payload=await response.json().catch(()=>({{}}));
        if(!response.ok)throw new Error(payload.error||("HTTP "+response.status));
        return payload;
      }}));
    }}
    const payload=await definitionCache.get(uri);
    if(requestedDefinition!==requestKey)return;
    definitionStatus.textContent="";
    renderDefinition(payload);
  }}catch(error){{
    definitionCache.delete(uri);
    if(requestedDefinition!==requestKey)return;
    definitionStatus.textContent="Could not load definition: "+error.message;
  }}
}}
function showDefinition(node){{
  if(!node){{definitionTitle.textContent="Definition";definitionUri.textContent="";clearDefinition("Select a node to load its definition.");return;}}
  definitionTitle.textContent=node.label;
  definitionUri.textContent=node.id;
  if(!node.definitions.length){{clearDefinition("No matching definition paragraph was found.");return;}}
  definitionChoice.replaceChildren(...node.definitions.map((uri,index)=>{{const option=document.createElement("option");option.value=uri;option.textContent="Definition "+(index+1)+(node.definitions.length>1?" of "+node.definitions.length:"");return option;}}));
  definitionChoice.hidden=node.definitions.length===1;
  loadDefinition(node,node.definitions[0]);
}}
definitionChoice.addEventListener("change",()=>{{const node=byId.get(selected);if(node)loadDefinition(node,definitionChoice.value);}});

function radius(d){{return d.depth===0?10:d.depth===1?7:5;}}
function linkPath(d){{
  const dx=d.target.x-d.source.x,dy=d.target.y-d.source.y;
  if(dy>8){{
    const middle=d.source.y+dy*.5;
    return "M"+d.source.x+","+d.source.y+"C"+d.source.x+","+middle+" "+d.target.x+","+middle+" "+d.target.x+","+d.target.y;
  }}
  const side=(d.source.x<=d.target.x?1:-1)*(42+Math.min(90,Math.abs(dx)*.2));
  return "M"+d.source.x+","+d.source.y+"C"+(d.source.x+side)+","+(d.source.y-45)+" "+(d.target.x+side)+","+(d.target.y+45)+" "+d.target.x+","+d.target.y;
}}
function updatePositions(){{
  linkSel.attr("d",linkPath);
  nodeSel.attr("transform",d=>"translate("+d.x+","+d.y+")");
}}
function arrangeLayers(width){{
  const layers=Array.from(d3.group(nodes,d=>d.depth??maxDepth+1),([depth,items])=>({{depth,items}})).sort((a,b)=>a.depth-b.depth);
  const lexical=(a,b)=>a.label.localeCompare(b.label)||a.id.localeCompare(b.id);
  layers.forEach(layer=>layer.items.sort(lexical));

  // A few barycentric sweeps reduce crossings without changing any node's level.
  for(let pass=0;pass<3;pass++){{
    const positions=new Map();
    layers.forEach(layer=>layer.items.forEach((node,index)=>positions.set(node.id,index)));
    for(let i=1;i<layers.length;i++){{
      layers[i].items.sort((a,b)=>{{
        const score=node=>{{const values=links.filter(e=>e.target===node&&positions.has(e.source.id)).map(e=>positions.get(e.source.id));return values.length?d3.mean(values):Infinity;}};
        return score(a)-score(b)||lexical(a,b);
      }});
    }}
    layers.slice(0,-1).reverse().forEach(layer=>{{
      const nextPositions=new Map();
      layers.forEach(candidate=>candidate.items.forEach((node,index)=>nextPositions.set(node.id,index)));
      layer.items.sort((a,b)=>{{
        const score=node=>{{const values=links.filter(e=>e.source===node&&nextPositions.has(e.target.id)).map(e=>nextPositions.get(e.target.id));return values.length?d3.mean(values):Infinity;}};
        return score(a)-score(b)||lexical(a,b);
      }});
    }});
  }}

  const left=96,right=70,top=64,layerGap=125,nodeGap=130;
  const widest=d3.max(layers,d=>d.items.length)??1;
  const usable=Math.max(width-left-right,(widest+1)*nodeGap);
  layers.forEach(layer=>layer.items.forEach((node,index)=>{{
    node.x=left+usable*(index+1)/(layer.items.length+1);
    node.y=top+layer.depth*layerGap;
  }}));
  return {{layers,width:left+usable+right,height:Math.max(600,top+maxDepth*layerGap+90)}};
}}
function setTooltip(event,d){{
  const outgoing=links.filter(e=>e.source.id===d.id).length;
  const incoming=links.filter(e=>e.target.id===d.id).length;
  tooltip.replaceChildren();
  const strong=document.createElement("strong"); strong.textContent=d.label;
  const archive=document.createElement("small"); archive.textContent=d.archive;
  const counts=document.createElement("small"); counts.textContent=outgoing+" dependencies · "+incoming+" dependents";
  tooltip.append(strong,archive,counts); tooltip.style.display="block";
  const box=frame.getBoundingClientRect();
  tooltip.style.left=Math.max(4,Math.min(event.clientX-box.left+12,box.width-370))+"px";
  tooltip.style.top=Math.max(4,event.clientY-box.top+12)+"px";
}}
function hideTooltip(){{tooltip.style.display="none";}}
function applySelection(id,force=false){{
  selected=force?id:(selected===id?null:id);
  const adjacent=new Set(selected?[selected]:[]);
  if(selected) links.forEach(e=>{{if(e.source.id===selected)adjacent.add(e.target.id);if(e.target.id===selected)adjacent.add(e.source.id);}});
  nodeSel.classed("dim",d=>selected&&!adjacent.has(d.id));
  linkSel.classed("active",e=>selected&&(e.source.id===selected||e.target.id===selected)).classed("dim",e=>selected&&e.source.id!==selected&&e.target.id!==selected);
  if(!selected){{selection.textContent="Click a node to highlight its dependencies and dependents.";showDefinition(null);return;}}
  const d=byId.get(selected),out=links.filter(e=>e.source.id===selected).length,inc=links.filter(e=>e.target.id===selected).length;
  selection.textContent=d.label+": "+out+" dependencies, "+inc+" dependents.";
  showDefinition(d);
}}
function focusNode(d){{
  applySelection(d.id,true);
  const width=frame.clientWidth,height=frame.clientHeight;
  svg.transition().duration(350).call(zoom.transform,d3.zoomIdentity.translate(width/2-d.x*1.25,height/2-d.y*1.25).scale(1.25));
}}
const zoom=d3.zoom().scaleExtent([.2,5]).on("zoom",event=>viewport.attr("transform",event.transform));
svg.call(zoom);

function draw(){{
  svg.selectAll("*").filter(function(){{return this.tagName!=="title"&&this.tagName!=="desc";}}).remove();
  const layout=arrangeLayers(Math.max(320,frame.clientWidth));
  svg.attr("viewBox","0 0 "+layout.width+" "+layout.height).attr("preserveAspectRatio","xMidYMin meet");
  const defs=svg.append("defs");
  defs.append("marker").attr("id","arrow").attr("viewBox","0 -5 10 10").attr("refX",16).attr("markerWidth",5).attr("markerHeight",5).attr("orient","auto").append("path").attr("d","M0,-5L10,0L0,5").attr("fill","currentColor");
  viewport=svg.append("g");
  const guides=viewport.append("g").attr("aria-hidden","true");
  guides.selectAll("line").data(layout.layers).join("line").attr("class","layer-line").attr("x1",82).attr("x2",layout.width-28).attr("y1",d=>d.items[0].y).attr("y2",d=>d.items[0].y);
  guides.selectAll("text").data(layout.layers).join("text").attr("class","layer-label").attr("x",72).attr("y",d=>d.items[0].y+4).text(d=>d.depth+(d.depth===1?" step":" steps"));
  linkSel=viewport.append("g").selectAll("path").data(links).join("path").attr("class","edge").attr("marker-end","url(#arrow)");
  nodeSel=viewport.append("g").selectAll("g").data(nodes).join("g").attr("class","node").attr("data-depth",d=>d.depth??"").on("pointerenter",setTooltip).on("pointermove",setTooltip).on("pointerleave",hideTooltip).on("click",(event,d)=>{{event.stopPropagation();applySelection(d.id);}}).call(d3.drag().on("drag",(event,d)=>{{d.x=event.x;d.y=event.y;updatePositions();}}));
  nodeSel.append("circle").attr("r",radius);
  nodeSel.append("text").attr("x",11).attr("y",4).text(d=>d.label.length>28?d.label.slice(0,27)+"…":d.label);
  updatePositions();
  if(selected)applySelection(selected,true);
}}
svg.on("click",()=>{{if(selected)applySelection(selected);}});
search.addEventListener("input",()=>{{
  const needle=search.value.trim().toLocaleLowerCase();
  if(!needle){{nodeSel.classed("dim",false);linkSel.classed("dim",false).classed("active",false);selected=null;selection.textContent="Click a node to highlight its dependencies and dependents.";showDefinition(null);return;}}
  const match=nodes.find(d=>d.label.toLocaleLowerCase().includes(needle)||d.id.toLocaleLowerCase().includes(needle));
  if(match)focusNode(match);
}});
let resizeTimer;
new ResizeObserver(()=>{{clearTimeout(resizeTimer);resizeTimer=setTimeout(draw,120);}}).observe(frame);
draw();
</script>
</body>
</html>
"""
