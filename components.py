import dash_html_components as html
import dash_bootstrap_components as dbc


def create_popover():
    return html.Div([
        dbc.Button("Help", id="popover-target", color="primary"),
        dbc.Popover(
            [
                dbc.PopoverBody(
                    html.Table([
                        html.Tr([
                            html.Td([
                                "Available"
                            ], className="p-1",
                                style={"background-color": "blue", "color": "white", "font-weight": "bold"}),
                        ]),
                        html.Tr([
                            html.Td([
                                "Booked"
                            ], className="p-1",
                                style={"background-color": "green", "color": "white", "font-weight": "bold"}),

                        ]),
                        html.Tr([
                            html.Td([
                                "Almost full"
                            ], className="p-1",
                                style={"background-color": "orange", "color": "white", "font-weight": "bold"}),
                        ]),
                        html.Tr([
                            html.Td([
                                "Full"
                            ], className="p-1",
                                style={"background-color": "Red", "color": "white", "font-weight": "bold"}),
                        ]),
                        html.Tr([
                            html.Td([
                                "Selected"
                            ], className="p-1",
                                style={"background-color": "grey", "color": "white", "font-weight": "bold"}),
                        ])
                    ])
                ),
            ],
            id="popover",
            is_open=False,
            target="popover-target",
            placement="below"
        ),
    ])