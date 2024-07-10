from collections import namedtuple
from math import sqrt

import bokeh.io
import bokeh.plotting
import networkx as nx
from bokeh import models

from .colormap import BokehGraphColorMap


class BokehGraph(object):
    """
    This is instanciated with a (one-mode) networkx graph object with
    BokehGraph(nx.Graph())

    working example:
    import networkx as nx
    graph = nx.barbell_graph(5,6)
    degrees = nx.degree(graph)
    nx.set_node_attributes(graph, dict(degrees), "degree")
    plot = BokehGraph(graph, width=800, height=600, inline=True)
    plot.layout(shrink_factor = 0.6)
    plot.draw(color_by="degree", palette="Category20", max_colors=2)


    The plot is drawn by BokehGraph.draw(node_color="firebrick")
        - node_color, line_color can be set to every value that bokeh
          recognizes, including a bokeh.colors.RGB instance. serveral other
          parameters can be found in the .draw method.


    """

    def __init__(
        self,
        graph,
        width=800,
        height=600,
        inline=True,
        hover_nodes=True,
        hover_edges=False,
    ):
        self.graph = graph

        self.width = width
        self.height = height

        self.hover_nodes = hover_nodes
        self.hover_edges = hover_edges

        self._layout = None
        self._nodes = None
        self._edges = None

        self.figure = None

        if nx.is_bipartite(self.graph) and nx.number_of_edges(self.graph) > 0:
            self.bipartite = 1
        else:
            self.bipartite = 0

        self.node_properties_lv0 = None
        self.node_properties_lv1 = None

        
        if self.bipartite:
            # lvl 0 set
            self.node_attributes_lv0 = sorted(
                {attr for _, data in self.graph.nodes(data=True) if data["bipartite"] == 0 for attr in data},
            )
            if self.hover_nodes:
                self._node_tooltips_lv0 = [("type", "node"), ("node", "@_node")]
                for attr in self.node_attributes_lv0:
                    self._node_tooltips_lv0.append((attr, f"@{attr}"))

            # lvl 1 set
            self.node_attributes_lv1 = sorted(
                {attr for _, data in self.graph.nodes(data=True) if data["bipartite"] == 1 for attr in data},
            )
            if self.hover_nodes:
                self._node_tooltips_lv1 = [("type", "node"), ("node", "@_node")]
                for attr in self.node_attributes_lv1:
                    self._node_tooltips_lv1.append((attr, f"@{attr}"))
        else:
            # lvl 0 set
            self.node_attributes_lv0 = sorted(
                {attr for _, data in self.graph.nodes(data=True) for attr in data},
            )
            if self.hover_nodes:
                self._node_tooltips_lv0 = [("type", "node"), ("node", "@_node")]
                for attr in self.node_attributes_lv0:
                    self._node_tooltips_lv0.append((attr, f"@{attr}"))


        self.edge_properties = None
        self.edge_attributes = sorted(
                {attr for _, _, data in self.graph.edges(data=True) for attr in data},
            )
        if self.hover_edges:
            self._edge_tooltips = [("type", "edge"), ("u", "@_u"), ("v", "@_v")]
            for attr in self.edge_attributes:
                self._edge_tooltips.append((attr, f"@{attr}"))

        # inline for jupyter notebooks
        if inline:
            bokeh.io.output_notebook(hide_banner=True)
            self.show = lambda x: bokeh.plotting.show(x, notebook_handle=True)
        else:
            self.show = lambda x: bokeh.plotting.show(x)

    def gen_edge_coordinates(self):
        if not self._layout:
            self.layout()

        xs = []
        ys = []
        val = namedtuple("edges", "xs ys")

        for edge in self.graph.edges():
            from_node = self._layout[edge[0]]
            to_node = self._layout[edge[1]]
            xs.append([from_node[0], to_node[0]])
            ys.append([from_node[1], to_node[1]])

        return val(xs=xs, ys=ys)

    def gen_node_coordinates(self):
        if not self._layout:
            self.layout()

        names, coords = zip(*self._layout.items())
        node = namedtuple("node", "name x y")

        return [node(name, x, y) for name, (x, y) in zip(names, coords)]

    def layout(self, layout=None, shrink_factor=0.8, iterations=50, scale=1, seed=None):
        self._nodes = None
        self._edges = None
        if not layout and not self.bipartite:
            self._layout = nx.spring_layout(
                self.graph,
                k=1 / (sqrt(self.graph.number_of_nodes() * shrink_factor)),
                iterations=iterations,
                scale=scale,
                seed=seed,
            )
        elif not layout and self.bipartite:
            self._layout = nx.bipartite_layout(
                self.graph,
                (node for node, data in self.graph.nodes(data=True) if data["bipartite"] == 1),
                align="vertical",
                )
        else:
            self._layout = layout
        return

    def prepare_figure(self):
        fig = bokeh.plotting.figure(
            width=self.width,
            height=self.height,
            tools=["box_zoom", "reset", "wheel_zoom", "pan"],
        )

        fig.toolbar.logo = None
        fig.axis.visible = False
        fig.xgrid.grid_line_color = None
        fig.ygrid.grid_line_color = None
        return fig

    def _render_edges(
        self,
        figure,
        edge_color,
        edge_palette,
        edge_size,
        edge_alpha,
        max_colors,
    ):
        if not self._edges:
            self._edges = self.gen_edge_coordinates()

        self.edge_properties = dict(
            xs=self._edges.xs,
            ys=self._edges.ys,
        )

        try:
            xs, ys = list(zip(*self.graph.edges()))
            self.edge_properties["_u"] = xs
            self.edge_properties["_v"] = ys
        except ValueError:
            # happens if the network has no edges
            pass

        for attr in self.edge_attributes:
            self.edge_properties[attr] = [
                data[attr] for _, _, data in self.graph.edges(data=True)
            ]

        # Set edge color; potentially based on attribute
        if edge_color in self.edge_attributes:
            colormap = BokehGraphColorMap(edge_palette, max_colors)
            self.edge_properties["_colormap"] = colormap.map(
                self.edge_properties[edge_color]
            )
            color = "_colormap"
        else:
            color = edge_color

        # Set edge size; potentially based on attribute
        if edge_alpha in self.edge_attributes:
            colormap = BokehGraphColorMap("numeric", max_colors)
            self.edge_properties["_edge_alpha"] = colormap.map(
                self.edge_properties[edge_alpha]
            )
            alpha = "_edge_alpha"
        else:
            alpha = edge_alpha

        # Draw Edges
        source_edges = bokeh.models.ColumnDataSource(self.edge_properties)

        edges = figure.multi_line(
            "xs",
            "ys",
            line_color=color,
            source=source_edges,
            alpha=alpha,
            line_width=edge_size,
        )

        if self.hover_edges:
            formatter = {tip: "printf" for tip, _ in self._edge_tooltips}
            hovertool = models.HoverTool(
                tooltips=self._edge_tooltips,
                formatters=formatter,
                renderers=[edges],
                line_policy="interp",
            )
            figure.add_tools(hovertool)

        return figure

    def _render_nodes(
        self,
        figure,
        node_alpha,
        node_size,
        node_color,
        node_palette,
        max_colors,
    ):
        if not self._nodes:
            self._nodes = self.gen_node_coordinates()

        if self.bipartite:
            nodes_lv1, nodes_lv0 = nx.bipartite.sets(self.graph)
            self.node_properties_lv0 = dict(xs=[], ys=[], names=[])
            self.node_properties_lv1 = dict(xs=[], ys=[], names=[])

            for node in self._nodes:
                if node.name in nodes_lv0:
                    target_dict = self.node_properties_lv0
                else:
                    target_dict = self.node_properties_lv1
                target_dict["xs"].append(node.x)
                target_dict["ys"].append(node.y)
                target_dict["names"].append(node.name)
        else:
            xs = [node.x for node in self._nodes]
            ys = [node.y for node in self._nodes]
            nodes_lv0 = [node.name for node in self._nodes]
            self.node_properties_lv0 = dict(
                xs=xs,
                ys=ys,
                _node=nodes_lv0,
            )

        nodes = self.graph.nodes

        # Color the nodes
        for attr in self.node_attributes_lv0:
            if not self.hover_nodes and attr != node_color:
                continue
            self.node_properties_lv0[attr] = [
                nodes[n][attr] for n in nodes_lv0
            ]
        if self.bipartite:
            for attr in self.node_attributes_lv1:
                if not self.hover_nodes and attr != node_color:
                    continue
                self.node_properties_lv1[attr] = [
                    nodes[n][attr] for n in nodes_lv1
                ]

        if node_color in self.node_attributes_lv0:
            colormap = BokehGraphColorMap(node_palette, max_colors)
            self.node_properties_lv0["_colormap"] = colormap.map(
                self.node_properties_lv0[node_color]
            )
            color = "_colormap"
        else:
            color = node_color
        if self.bipartite:
            if node_color in self.node_attributes_lv1:
                colormap = BokehGraphColorMap(node_palette, max_colors)
                self.node_properties_lv1["_colormap"] = colormap.map(
                    self.node_properties_lv1[node_color]
                )
                color = "_colormap"
            else:
                color = node_color


        source_nodes_lv0 = bokeh.models.ColumnDataSource(self.node_properties_lv0)
        nodes_lv0 = figure.scatter(
            "xs",
            "ys",
            marker="circle",
            fill_color=color,
            line_color=color,
            source=source_nodes_lv0,
            alpha=node_alpha,
            size=node_size,
        )
        if self.bipartite:
            source_nodes_lv1 = bokeh.models.ColumnDataSource(self.node_properties_lv1)
            nodes_lv1 = figure.scatter(
                "xs",
                "ys",
                marker="square",
                fill_color=color,
                line_color=color,
                source=source_nodes_lv1,
                alpha=node_alpha,
                size=node_size,
            )

        if self.hover_nodes:
            formatter = {tip: "printf" for tip, _ in self._node_tooltips_lv0}
            hovertool = models.HoverTool(
                tooltips=self._node_tooltips_lv0,
                formatters=formatter,
                renderers=[nodes_lv0],
                attachment="vertical",
            )
            figure.add_tools(hovertool)
            if self.bipartite:
                formatter = {tip: "printf" for tip, _ in self._node_tooltips_lv1}
                hovertool = models.HoverTool(
                    tooltips=self._node_tooltips_lv1,
                    formatters=formatter,
                    renderers=[nodes_lv1],
                    attachment="vertical",
                )
                figure.add_tools(hovertool)

        return figure

    def render(
        self,
        node_color,
        node_palette,
        node_size,
        node_alpha,
        edge_color,
        edge_palette,
        edge_size,
        edge_alpha,
        max_colors,
    ):
        figure = self.prepare_figure()

        figure = self._render_edges(
            figure=figure,
            edge_color=edge_color,
            edge_palette=edge_palette,
            edge_alpha=edge_alpha,
            edge_size=edge_size,
            max_colors=max_colors,
        )

        figure = self._render_nodes(
            figure=figure,
            node_color=node_color,
            node_palette=node_palette,
            node_size=node_size,
            node_alpha=node_alpha,
            max_colors=max_colors,
        )

        return figure

    def draw(
        self,
        node_color="firebrick",
        node_palette="Category20",
        node_size=9,
        node_alpha=0.7,
        edge_color="navy",
        edge_palette="viridis",
        edge_alpha=0.3,
        edge_size=1,
        max_colors=-1,
    ):
        figure = self.render(
            node_color=node_color,
            node_palette=node_palette,
            node_size=node_size,
            node_alpha=node_alpha,
            edge_color=edge_color,
            edge_palette=edge_palette,
            edge_size=edge_size,
            edge_alpha=edge_alpha,
            max_colors=max_colors,
        )
        self.show(figure)
