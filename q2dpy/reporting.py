"""Creates .ipynb file of results for visualization in jupiter notebooks"""

from datetime import datetime
from pathlib import Path

import h5py
import nbformat as nbf

import config


def hecras_calibration_report(output_dir, filename):
    phdf_filename = Path(config.phdf_filename)

    mod_results = h5py.File(phdf_filename, 'r')
    ras_info = mod_results['Results/Summary/Compute Processes']
    plan_params = mod_results['Plan Data/Plan Parameters']
    plan_info = mod_results['Plan Data/Plan Information']
    up_bc = mod_results[
        f'Results/Unsteady/Output/Output Blocks/Base Output/Unsteady Time Series/Boundary Conditions/{config.us_bc}']
    dwn_bc = mod_results[
        f'Event Conditions/Unsteady/Boundary Conditions/Normal Depths/2D: {config.perimeter} BCLine: {config.ds_bc}']

    ras_2d_param_lst = ['2D Boundary Condition Ramp Up Fraction',
                        '2D Boundary Condition Volume Check',
                        '2D Cores (per mesh)',
                        '2D Coriolis',
                        '2D Equation Set',
                        '2D Initial Conditions Ramp Up Time (hrs)',
                        '2D Latitude for Coriolis',
                        '2D Longitudinal Mixing Coefficient',
                        '2D Matrix Solver',
                        '2D Maximum Iterations',
                        '2D Names',
                        '2D Number of Time Slices',
                        '2D Only',
                        '2D Smagorinsky Mixing Coefficient',
                        '2D Theta',
                        '2D Theta Warmup',
                        '2D Transverse Mixing Coefficient',
                        '2D Turbulence Formulation',
                        '2D Volume Tolerance',
                        '2D Water Surface Tolerance',
                        'Gravity']

    ras_version = ras_info[0][4].decode()
    ras_location = ras_info[0][1].decode()
    project = plan_info.attrs['Project Title'].decode()
    plan_name = plan_info.attrs['Plan Name'].decode()
    geometry_name = plan_info.attrs['Geometry Title'].decode()
    flow_name = plan_info.attrs['Flow Title'].decode()
    start_time = plan_info.attrs['Simulation Start Time'].decode()
    end_time = plan_info.attrs['Simulation End Time'].decode()
    comp_time_step = plan_info.attrs['Computation Time Step Base'].decode()
    output_time_step = plan_info.attrs['Base Output Interval'].decode()
    params_2d = [plan_params.attrs[i] for i in ras_2d_param_lst]
    flow_units = up_bc.attrs['Flow'].decode()
    stage_units = up_bc.attrs['Stage'].decode()

    calibration_params = config.Man_n_params

    up_bc_inflow = up_bc[:, 1]
    dwn_bc_norm = dwn_bc[0]

    params_2d_strng = [p + ' = ' + str(v) + '\n' for p, v in zip(ras_2d_param_lst, params_2d)]
    params_2d_strng = ''.join(params_2d_strng)

    nb = nbf.v4.new_notebook()

    nbtitle_heading = """\
    # Model Calibration Report
    ## Model Type: HEC-RAS
    ### Model Version: {0}
    ### Model Location: {1}
    ### Report Created: {2}
    
    ### Calibration Q: {3} {4}""".format(ras_version, ras_location, datetime.now().strftime('%Y-%m-%d'),
                                         up_bc_inflow[-1], flow_units)

    btxt_1 = """\
    #### HEC-RAS Plan Info
    * HEC-RAS Project: {0}
    * Plan Name: {1}
    * Geometry Name: {2}
    * Flow Name: {3}
    * Simulation Start Time: {4}
    * Simulation End Time: {5}
    * Simulation Time Step: {6}
    * Output Time Step: {7}""".format(project, plan_name, geometry_name, flow_name, start_time, end_time,
                                      comp_time_step, output_time_step)

    btxt_2 = """\
    #### 2D Model Boundary Conditions:
    Upstream Flow Hydrograph: {0}
    Downstream Normal Depth: slope {1}""".format(str(up_bc_inflow), dwn_bc_norm)

    btxt_3 = """\
    #### HEC-RAS 2D Simulation Parameters
    {0}""".format(params_2d_strng)

    code1 = """\
    import pandas as pd
    from pathlib import Path
    from itables import init_notebook_mode
    import plotly.express as px
    import plotly.graph_objects as go
    from plotly.subplots import make_subplots
    init_notebook_mode(all_interactive=True)"""

    code2 = """\
    output_dir = Path(r'{0}')
    ghdf_filename = Path(output_dir / 'WFRC_lidar.g01.hdf')
    phdf_filename = Path(output_dir / 'WFRC_lidar.p01.hdf')
    uhdf_filename = Path(output_dir / 'WFRC_lidar.u01.hdf')
    wse_filename = Path(output_dir / 'wse_profiles.csv')
    mruns_filename = Path(output_dir / 'model_iterations.csv')""".format(str(output_dir))

    code3 = """\
    wse = pd.read_csv(wse_filename)
    wse = wse.sort_values(by='Channel_Distance')
    mruns = pd.read_csv(mruns_filename)
    bst_run = mruns[mruns['Obj_Func_Value'] == mruns['Obj_Func_Value'].min()]
    cal_params = {0}""".format(calibration_params)

    code4 = """\
    mruns_cal_params = mruns[cal_params + ['iteration', 'Obj_Func_Value']]
    mruns_cp_tidy = pd.melt(mruns_cal_params,
                            ['iteration', 'Obj_Func_Value'],
                            var_name='Calibration_Region',
                            value_name="Manning's n")
    wse_tidy = pd.melt(wse,
                       ['Cell_Index', 'ID', 'Channel_Distance', 'Elev_m'],
                       var_name='Model_Run',
                       value_name='Modeled_wse')"""

    tbl_title1 = """\
    #### Table 1: Parameter and objective function values for all model runs"""

    code5 = """\
    mruns"""

    tbl_title2 = """\
    #### Table 2: Parameter and objective function values for the best model run"""

    code6 = """\
    bst_run"""

    tbl_title3 = """\
    #### Table 3: Water surface elevation profiles for all model runs"""

    code7 = """\
    wse"""

    code8 = """\
    fig = px.line(mruns_cp_tidy, x='iteration', y="Manning's n", facet_col='Calibration_Region')
    fig.show(renderer='notebook')"""

    code9 = """\
    fig = px.histogram(mruns_cp_tidy, x="Manning's n", nbins=12, facet_col='Calibration_Region')
    fig.show(renderer='notebook')"""

    code10 = """\
    fig = go.Figure(data=go.Scatter(x=mruns['iteration'], y=mruns['Obj_Func_Value'], mode='lines+markers'))
    fig.update_layout(title='Results of Minimization Function (Nelder-Mead Algorithm)',
                       xaxis_title='Model Run',
                       yaxis_title='RMSE')
    fig.show(renderer='notebook')"""

    code11 = """\
    fig = px.line(wse_tidy, x='Channel_Distance', y='Modeled_wse', color='Model_Run',
                 title='All Modeled WSE Profiles vs Measured WSE Points',
                 template='simple_white',
                 labels={
                     "Modeled_wse":"Water Surface Elevation (m)",
                     "Channel_Distance":"Distance Downstream (m)"
                 })
    for code, group in wse.groupby("CODE"):
        fig.add_trace(go.Scatter(x=group["Channel_Distance"], y=group["Elev_m"], name=code, mode='markers',
          hovertemplate="Code=%s<br>Channel_Distance=%%{x}<br>Elev_m=%%{y}<extra></extra>"% code))
    fig.show(renderer='notebook')"""

    code12 = """\
    fig = go.Figure()
    fig.add_trace(
        go.Scatter(
            x=wse['Channel_Distance'],
            y=wse['Elev_m'],
            mode='markers',
            name='Measured WSE',
            showlegend=True)
    )
    fig.add_trace(
        go.Scatter(
            x=wse['Channel_Distance'],
            y=wse['I{0}'.format(bst_run['iteration'].iloc[0])],
            mode='lines',
            name='Calibrated Model WSE',
            showlegend=True)
    )
    fig.update_layout(title='Water Surface Elevation Profile of Calibrated Model',
                       xaxis_title='Distance Downstream (m)',
                       yaxis_title='Water Surface Elevation (m)')
    fig.show(renderer='notebook')"""

    code13 = """\
    fig = make_subplots(rows=1, cols=2, shared_yaxes=True)
    fig.add_trace(
        go.Scatter(x=wse['Channel_Distance'], y=wse['I{0}'.format(bst_run['iteration'].iloc[0])] - wse['Elev_m'], mode='markers', name='WSE Error'),
        row=1, col=1
    )
    fig.add_trace(
        go.Box(y=wse['I{0}'.format(bst_run['iteration'].iloc[0])] - wse['Elev_m'], boxpoints='all', name='WSE Error Distribution'),
        row=1, col=2
    )
    fig.update_yaxes(title_text='Water Surface Elevation Model Error (m)',
                       row=1,
                       col=1)
    fig.update_xaxes(title_text='Downstream Distance (m)', row=1, col=1)
    fig.show(renderer='notebook')"""

    nb['cells'] = [nbf.v4.new_markdown_cell(nbtitle_heading),
                   nbf.v4.new_markdown_cell(btxt_1),
                   nbf.v4.new_markdown_cell(btxt_2),
                   nbf.v4.new_markdown_cell(btxt_3),
                   nbf.v4.new_code_cell(code1),
                   nbf.v4.new_code_cell(code2),
                   nbf.v4.new_code_cell(code3),
                   nbf.v4.new_code_cell(code4),
                   nbf.v4.new_markdown_cell(tbl_title1),
                   nbf.v4.new_code_cell(code5),
                   nbf.v4.new_markdown_cell(tbl_title2),
                   nbf.v4.new_code_cell(code6),
                   nbf.v4.new_markdown_cell(tbl_title3),
                   nbf.v4.new_code_cell(code7),
                   nbf.v4.new_code_cell(code8),
                   nbf.v4.new_code_cell(code9),
                   nbf.v4.new_code_cell(code10),
                   nbf.v4.new_code_cell(code11),
                   nbf.v4.new_code_cell(code12),
                   nbf.v4.new_code_cell(code13)]

    nb_fname = Path(output_dir / filename)

    with open(nb_fname, 'w') as f:
        nbf.write(nb, f)


def hecras_indirectQ_report(output_dir, filename):
    phdf_filename = Path(config.phdf_filename)

    mod_results = h5py.File(phdf_filename, 'r')
    ras_info = mod_results['Results/Summary/Compute Processes']
    plan_params = mod_results['Plan Data/Plan Parameters']
    plan_info = mod_results['Plan Data/Plan Information']
    up_bc = mod_results[
        f'Results/Unsteady/Output/Output Blocks/Base Output/Unsteady Time Series/Boundary Conditions/{config.us_bc}']
    dwn_bc = mod_results[
        f'Event Conditions/Unsteady/Boundary Conditions/Normal Depths/2D: {config.perimeter} BCLine: {config.ds_bc}']

    ras_2d_param_lst = ['2D Boundary Condition Ramp Up Fraction',
                        '2D Boundary Condition Volume Check',
                        '2D Cores (per mesh)',
                        '2D Coriolis',
                        '2D Equation Set',
                        '2D Initial Conditions Ramp Up Time (hrs)',
                        '2D Latitude for Coriolis',
                        '2D Longitudinal Mixing Coefficient',
                        '2D Matrix Solver',
                        '2D Maximum Iterations',
                        '2D Names',
                        '2D Number of Time Slices',
                        '2D Only',
                        '2D Smagorinsky Mixing Coefficient',
                        '2D Theta',
                        '2D Theta Warmup',
                        '2D Transverse Mixing Coefficient',
                        '2D Turbulence Formulation',
                        '2D Volume Tolerance',
                        '2D Water Surface Tolerance',
                        'Gravity']

    ras_version = ras_info[0][4].decode()
    ras_location = ras_info[0][1].decode()
    project = plan_info.attrs['Project Title'].decode()
    plan_name = plan_info.attrs['Plan Name'].decode()
    geometry_name = plan_info.attrs['Geometry Title'].decode()
    flow_name = plan_info.attrs['Flow Title'].decode()
    start_time = plan_info.attrs['Simulation Start Time'].decode()
    end_time = plan_info.attrs['Simulation End Time'].decode()
    comp_time_step = plan_info.attrs['Computation Time Step Base'].decode()
    output_time_step = plan_info.attrs['Base Output Interval'].decode()
    params_2d = [plan_params.attrs[i] for i in ras_2d_param_lst]
    flow_units = up_bc.attrs['Flow'].decode()
    stage_units = up_bc.attrs['Stage'].decode()

    calibration_params = config.Man_n_params + config.Q_params

    up_bc_inflow = up_bc[:, 1].max()
    dwn_bc_norm = dwn_bc[0]

    params_2d_strng = [p + ' = ' + str(v) + '\n' for p, v in zip(ras_2d_param_lst, params_2d)]
    params_2d_strng = ''.join(params_2d_strng)

    nb = nbf.v4.new_notebook()

    nbtitle_heading = """\
    # Indirect Discharge Calculation Report
    ## Model Type: HEC-RAS
    ### Model Version: {0}
    ### Model Location: {1}
    ### Report Created: {2}
    ### Flow Units: {3}""".format(ras_version, ras_location, datetime.now().strftime('%Y-%m-%d'), flow_units)

    btxt_1 = """\
    #### HEC-RAS Plan Info
    * HEC-RAS Project: {0}
    * Plan Name: {1}
    * Geometry Name: {2}
    * Flow Name: {3}
    * Simulation Start Time: {4}
    * Simulation End Time: {5}
    * Simulation Time Step: {6}
    * Output Time Step: {7}""".format(project, plan_name, geometry_name, flow_name, start_time, end_time,
                                      comp_time_step, output_time_step)

    btxt_2 = """\
    #### 2D Model Boundary Conditions:
    Upstream Flow Hydrograph: Variable
    Downstream Normal Depth: slope {1}""".format(str(up_bc_inflow), dwn_bc_norm)

    btxt_3 = """\
    #### HEC-RAS 2D Simulation Parameters
    {0}""".format(params_2d_strng)

    code1 = """\
    import pandas as pd
    from pathlib import Path
    import h5py
    from itables import init_notebook_mode
    import plotly.express as px
    import plotly.graph_objects as go
    import plotly.figure_factory as ff
    from plotly.subplots import make_subplots
    init_notebook_mode(all_interactive=True)"""

    code2 = """\
    output_dir = Path(r'{0}')
    ghdf_filename = Path(output_dir / 'WestForkRockCree.g02.hdf')
    phdf_filename = Path(output_dir / 'WestForkRockCree.p02.hdf')
    uhdf_filename = Path(output_dir / 'WestForkRockCree.u02.hdf')
    wse_filename = Path(output_dir / 'wse_profiles.csv')
    mruns_filename = Path(output_dir / 'model_iterations.csv')""".format(str(output_dir))

    code3 = """\
    wse = pd.read_csv(wse_filename)
    wse = wse.sort_values(by='Channel_Distance')
    mruns = pd.read_csv(mruns_filename)
    bst_run = mruns[mruns['Obj_Func_Value'] == mruns['Obj_Func_Value'].min()]
    cal_params = {0}""".format(calibration_params)

    code4 = """\
    mruns_cal_params = mruns[cal_params + ['iteration', 'Obj_Func_Value']]
    mruns_cp_tidy = pd.melt(mruns_cal_params,
                            ['iteration', 'Obj_Func_Value', '{0}'],
                            var_name='Calibration_Region',
                            value_name="Manning's n")
    wse_tidy = pd.melt(wse,
                       ['Cell_Index', 'ID', 'Channel_Distance', 'Elev_m'],
                       var_name='Model_Run',
                       value_name='Modeled_wse')""".format(calibration_params[-1])

    tbl_title1 = """\
    #### Table 1: Parameter and objective function values for all model runs"""

    code5 = """\
    mruns"""

    tbl_title2 = """\
    #### Table 2: Parameter and objective function values for the best model run"""

    code6 = """\
    bst_run"""

    tbl_title3 = """\
    #### Table 3: Water surface elevation profiles for all model runs"""

    code7 = """\
    wse"""

    code8 = """\
    fig = px.line(mruns_cp_tidy, x='iteration', y="Manning's n", facet_col='Calibration_Region')
    fig.show(renderer='notebook')"""

    code9 = """\
    fig = px.histogram(mruns_cp_tidy, x="Manning's n", nbins=12, facet_col='Calibration_Region')
    fig.show(renderer='notebook')"""

    code10 = """\
    fig = go.Figure(data=go.Scatter(x=mruns['iteration'], y=mruns['Obj_Func_Value'], mode='lines+markers'))
    fig.update_layout(title='Results of Minimization Function (Nelder-Mead Algorithm)',
                       xaxis_title='Model Run',
                       yaxis_title='RMSE')
    fig.show(renderer='notebook')"""

    code11 = """\
    fig = px.line(wse_tidy, x='Channel_Distance', y='Modeled_wse', color='Model_Run',
                 title='All Modeled WSE Profiles vs Measured WSE Points',
                 template='simple_white',
                 labels={
                     "Modeled_wse":"Water Surface Elevation (m)",
                     "Channel_Distance":"Distance Downstream (m)"
                 })
    for code, group in wse.groupby("CODE"):
        fig.add_trace(go.Scatter(x=group["Channel_Distance"], y=group["Elev_m"], name=code, mode='markers',
          hovertemplate="Code=%s<br>Channel_Distance=%%{x}<br>Elev_m=%%{y}<extra></extra>"% code))
    fig.show(renderer='notebook')"""

    code12 = """\
    fig = go.Figure()
    fig.add_trace(
        go.Scatter(
            x=wse['Channel_Distance'],
            y=wse['Elev_m'],
            mode='markers',
            name='Measured WSE',
            showlegend=True)
    )
    fig.add_trace(
        go.Scatter(
            x=wse['Channel_Distance'],
            y=wse['I{0}'.format(bst_run['iteration'].iloc[0])],
            mode='lines',
            name='Calibrated Model WSE',
            showlegend=True)
    )
    fig.update_layout(title='Water Surface Elevation Profile of Calibrated Model',
                       xaxis_title='Distance Downstream (m)',
                       yaxis_title='Water Surface Elevation (m)')
    fig.show(renderer='notebook')"""

    code13 = """\
    fig = make_subplots(rows=1, cols=2, shared_yaxes=True)
    fig.add_trace(
        go.Scatter(x=wse['Channel_Distance'], y=wse['I{0}'.format(bst_run['iteration'].iloc[0])] - wse['Elev_m'], mode='markers', name='WSE Error'),
        row=1, col=1
    )
    fig.add_trace(
        go.Box(y=wse['I{0}'.format(bst_run['iteration'].iloc[0])] - wse['Elev_m'], boxpoints='all', name='WSE Error Distribution'),
        row=1, col=2
    )
    fig.update_yaxes(title_text='Water Surface Elevation Model Error (m)',
                       row=1,
                       col=1)
    fig.update_xaxes(title_text='Downstream Distance (m)', row=1, col=1)
    fig.show(renderer='notebook')"""

    code14 = """\
    fig = ff.create_distplot([mruns['{0}'].loc[14:].tolist()], ['Q Distribution'])
    fig.update_layout(title='Distribution of Modeled Discharges based on HWMs',
                       xaxis_title='Discharge (cms)',
                       yaxis_title='Probability of Occurance')
    fig.show(renderer='notebook')""".format(calibration_params[-1])

    code15 = """\
    print(f"The median Q is: {mruns[{cal_params[-1]}].median()} m^3/s --- {mruns['Q'].median() / 0.3048**3} cfs")
    print(f"The 10th EP Q is: {mruns[{cal_params[-1]}].quantile(q=0.9)} m^3/s --- {mruns['{0}'].quantile(q=0.9) / 0.3048**3} cfs")
    print(f"The 90th EP Q is: {mruns[{cal_params[-1]}].quantile(q=0.1)} m^3/s --- {mruns['{0}'].quantile(q=0.1) / 0.3048**3} cfs")
    print(f"The mean Q is: {mruns[{cal_params[-1]}].mean()} m^3/s --- {mruns['Q'].mean() / 0.3048**3} cfs")
    print(f"The standard deviation of Q is: {mruns[cal_params[-1]].std()} m^3/s --- {mruns[cal_params[-1]].std() / 0.3048**3} cfs")"""

    nb['cells'] = [nbf.v4.new_markdown_cell(nbtitle_heading),
                   nbf.v4.new_markdown_cell(btxt_1),
                   nbf.v4.new_markdown_cell(btxt_2),
                   nbf.v4.new_markdown_cell(btxt_3),
                   nbf.v4.new_code_cell(code1),
                   nbf.v4.new_code_cell(code2),
                   nbf.v4.new_code_cell(code3),
                   nbf.v4.new_code_cell(code4),
                   nbf.v4.new_markdown_cell(tbl_title1),
                   nbf.v4.new_code_cell(code5),
                   nbf.v4.new_markdown_cell(tbl_title2),
                   nbf.v4.new_code_cell(code6),
                   nbf.v4.new_markdown_cell(tbl_title3),
                   nbf.v4.new_code_cell(code7),
                   nbf.v4.new_code_cell(code8),
                   nbf.v4.new_code_cell(code9),
                   nbf.v4.new_code_cell(code10),
                   nbf.v4.new_code_cell(code11),
                   nbf.v4.new_code_cell(code12),
                   nbf.v4.new_code_cell(code13),
                   nbf.v4.new_code_cell(code14),
                   nbf.v4.new_code_cell(code15)]

    nb_fname = Path(output_dir / filename)

    with open(nb_fname, 'w') as f:
        nbf.write(nb, f)

# if __name__ == '__main__':
#    output_dir = Path(r'D:\HEC-RAS Projects\WF_Rock_Cr\20220927_Calibration')
#    hecras_report(output_dir)
