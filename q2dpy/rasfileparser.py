"""Module responsible for changing RAS plan and flow save files"""

import math
import re

import numpy as np

import config


class FlowFileParser:
    """Makes changes to flow file, e.g. teton_springhill.u01"""

    def __init__(self, flowfl_pth):
        self.flowfile = flowfl_pth
        self._lines = None

    def _create_dict(self):
        """creates dictionary of flow at timesteps?"""
        out_dict = {}

        with open(self.flowfile) as f:
            lines = f.readlines()
            self._lines = lines
            # print(lines)
            hydrograph = []
            for l in lines:
                if re.match(r'\s', l):
                    hydgrph = [hydrograph.append(char.strip()) for char in l.split()]
                else:
                    stdata = [char.strip() for char in l.split('=')]
                    # print(stdata)
                if len(stdata) > 2:
                    out_dict['='.join(stdata[:-1])] = stdata[-1]
                else:
                    out_dict[stdata[0]] = stdata[-1]
            out_dict['Flow Hydrograph'] = [len(hydrograph), np.array(hydrograph, dtype=float)]
        return out_dict

    def update_unsteady_flow(self, hydrograph):
        """Depreciated function for updating flow"""

        time_interval_dict = {'H': '1HOUR'}
        interv = time_interval_dict[hydrograph.index.freqstr]
        hydrgrph = [len(hydrograph), hydrograph.values]
        # print(hydrgrph)

        self._param_dict['Interval'] = interv
        self._param_dict['Flow Hydrograph'] = hydrgrph

        formatted_hydrgrph = self.format_hydrograph_input(hydrgrph[0], hydrgrph[1])
        # print(formatted_hydrgrph)

        str_ind = []
        for i, line in enumerate(self._lines):
            if 'Flow Hydrograph=' in line:
                str_ind.append(i)
                i_sub = i + 1
                l_sub = self._lines[i_sub]
                while re.match(r'\s', l_sub) is not None:
                    str_ind.append(i_sub)
                    i_sub += 1
                    l_sub = self._lines[i_sub]
            else:
                pass

        # print(str_ind)

        top_blck = self._lines[:str_ind[0]]
        top_blck[-1] = '{0}={1}\n'.format('Interval', self._param_dict['Interval'])
        # print(top_blck)
        btm_blck = self._lines[(str_ind[-1] + 1):]
        # print(btm_blck)
        top_blck.extend(formatted_hydrgrph)
        # print(top_blck)

        top_blck.extend(btm_blck)
        self._lines = top_blck

        updt_txt = ''.join(top_blck)
        with open(self.flowfile, 'r+') as f:
            f.seek(0)
            f.write(updt_txt)
            f.truncate()

    def format_hydrograph_input(self, new_q_val):
        """Writes a new inflow hydrograph (m^3/s) to the upstream boundary condition
        (config.us_bc) of the flow file.

        Constant discharge, or a ramp from 0 that holds the peak for the last hour
        (hydrograph_ramp). With change_sim_time the number of values becomes
        sim_time_hr * 4 (15-minute interval); otherwise the existing count is kept.
        """
        q_val = round(new_q_val[0] if isinstance(new_q_val, list) else new_q_val, 3)
        print(f"Q= {q_val}")
        lines = self._read_lines()

        head = self._bc_key_line(lines, config.us_bc, 'Flow Hydrograph=')
        old_entries = int(lines[head].split('=', 1)[1].split()[0])
        old_rows = int(math.ceil(old_entries / 10))

        if config.change_sim_time is True:
            interval_line = self._bc_key_line(lines, config.us_bc, 'Interval=')
            interval = lines[interval_line].split('=', 1)[1].strip()
            if interval != '15MIN':
                raise ValueError(f"change_sim_time assumes a 15MIN hydrograph interval, but boundary "
                                 f"'{config.us_bc}' uses {interval}.")
            entries = config.sim_time_hr * 4 + 1  # e.g. 3 hr -> 13 values, 0:00 to 3:00
        else:
            entries = old_entries

        if config.hydrograph_ramp is True:
            if entries < 5:
                raise ValueError(f"hydrograph_ramp needs at least 5 values, the hydrograph has {entries}.")
            increment = q_val / (entries - 1)
            new_hydrogrh = []
            for v in range(entries):
                if v == 0:
                    new_hydrogrh.append(0)
                elif v >= entries - 4:  # hold the peak for the last hour
                    new_hydrogrh.append(q_val)
                else:
                    new_hydrogrh.append(round(v * increment, 3))
        else:
            new_hydrogrh = [q_val] * entries

        # 10 values per row, each right-aligned in an 8-character field
        new_rows = []
        for r in range(0, entries, 10):
            row = ''
            for v in new_hydrogrh[r:r + 10]:
                txt = str(v)
                if len(txt) > 8:
                    raise ValueError(f"Discharge {txt} does not fit the 8-character hydrograph field.")
                row += f"{txt:>8}"
            new_rows.append(row + '\n')

        # replace the count and the old data rows (the number of rows may change)
        lines[head] = f"Flow Hydrograph= {entries} \n"
        lines[head + 1:head + 1 + old_rows] = new_rows

        self._write_lines(lines)
        print("Hydrograph successfully changed")

    # ------------------------------------------------- boundary friction slopes
    @staticmethod
    def _bc_key_line(lines, bc_name, key):
        """Index of the first line starting with `key` inside the block of boundary
        condition `bc_name` (from its 'Boundary Location=' line to the next one).

        The BC name is field 8 of the 'Boundary Location=' line and the 2D flow area
        is field 6. If the same BC name is used on more than one flow area, the one
        matching config.perimeter is used. Raises ValueError if the BC or key is not found.
        """
        starts = [i for i, ln in enumerate(lines) if ln.startswith('Boundary Location=')]
        matches = []
        for i in starts:
            fields = [f.strip() for f in lines[i].split('=', 1)[1].split(',')]
            if len(fields) > 7 and fields[7] == bc_name:
                matches.append((i, fields[5]))
        if len(matches) > 1:
            matches = [m for m in matches if m[1] == config.perimeter]
        if len(matches) != 1:
            raise ValueError(f"Boundary condition '{bc_name}' (flow area '{config.perimeter}') found "
                             f"{len(matches)} times in {config.flow_filename}; expected once. "
                             "Check us_bc, ds_bc and perimeter in [labels].")
        first = matches[0][0]
        nxt = next((i for i in starts if i > first), len(lines))
        for i in range(first + 1, nxt):
            if lines[i].startswith(key):
                return i
        raise ValueError(f"'{key}' not found under boundary condition '{bc_name}' in {config.flow_filename}.")

    @staticmethod
    def _read_lines():
        with open(config.flow_filename, 'r', encoding='utf-8') as flow_plan:
            return flow_plan.readlines()

    @staticmethod
    def _write_lines(lines):
        with open(config.flow_filename, 'w', encoding='utf-8') as flow_plan:
            flow_plan.writelines(lines)

    def read_us_EGslope(self):
        """returns energy gradient at upstream boundary condition"""
        lines = self._read_lines()
        num = self._bc_key_line(lines, config.us_bc, 'Flow Hydrograph Slope=')
        return float(lines[num].split('=', 1)[1].strip())

    def update_us_EGslope(self, us_slope):
        """updates energy gradient at upstream boundary condition"""
        slope_val = f"{round(us_slope, 5):.5f}"  # fixed format, never scientific notation
        lines = self._read_lines()
        num = self._bc_key_line(lines, config.us_bc, 'Flow Hydrograph Slope=')
        lines[num] = f'Flow Hydrograph Slope= {slope_val} \n'
        self._write_lines(lines)
        print(f"US Friction Slope changed to {slope_val}")

    def read_ds_EGslope(self):
        """returns energy gradient at downstream boundary condition"""
        lines = self._read_lines()
        num = self._bc_key_line(lines, config.ds_bc, 'Friction Slope=')
        return float(lines[num].split('=', 1)[1].split(',')[0].strip())

    def update_ds_EGslope(self, ds_slope):
        """updates energy gradient at downstream boundary condition"""
        slope_val = f"{round(ds_slope, 5):.5f}"  # fixed format, never scientific notation
        lines = self._read_lines()
        num = self._bc_key_line(lines, config.ds_bc, 'Friction Slope=')
        rest = lines[num].rstrip('\n').split('=', 1)[1].split(',', 1)
        tail = f",{rest[1]}" if len(rest) > 1 else ''  # keep ",0" (RAS 6.x); RAS 7 has none
        lines[num] = f'Friction Slope={slope_val}{tail}\n'
        self._write_lines(lines)
        print(f"DS Friction Slope changed to {slope_val}")


class PlanFileParser:
    """Makes changes to plan file, e.g. teton_springhill.p01"""

    def __init__(self, planfl_pth):
        self.planfile = planfl_pth
        self._lines = None
        self._param_dict = self._create_dict()
        self.start_date = config.start_date
        self.start_time = config.start_time
        self.end_date = config.end_date
        self.end_time = config.end_time
        self.comp_interval = config.computation_interval

    def _create_dict(self):
        """again, unsure why this is here"""
        out_dict = {}
        with open(self.planfile) as f:
            lines = f.readlines()
            self._lines = lines
            for l in lines:
                stdata = [char.strip() for char in l.split('=')]

                if len(stdata) < 2:
                    pass
                else:
                    out_dict[stdata[0]] = stdata[1]
        return out_dict

    @staticmethod
    def _key_line(lines, key):
        """Index of the one line in the plan file that starts with `key`."""
        found = [i for i, ln in enumerate(lines) if ln.startswith(key)]
        if len(found) != 1:
            raise ValueError(f"'{key}' found {len(found)} times in {config.plan_filename}; expected once.")
        return found[0]

    def update_datetime(self):
        """Updates simulation date and time in plan file"""
        sim_date = f"Simulation Date={self.start_date},{self.start_time},{self.end_date},{self.end_time}\n"
        comp_int = f"Computation Interval={self.comp_interval}\n"

        with open(config.plan_filename, 'r', encoding='utf-8') as plan_file:
            lines = plan_file.readlines()
        lines[self._key_line(lines, 'Simulation Date=')] = sim_date
        lines[self._key_line(lines, 'Computation Interval=')] = comp_int

        with open(config.plan_filename, 'w', encoding='utf-8') as plan_file:
            plan_file.writelines(lines)

    def update_simulation_date(self, hydrograph):  # not currently in use
        """updates simulation date, depreciated"""

        # 2400 time replacement
        def tm_replace(in_time_str):
            if in_time_str == '0000':
                out_time_str = '2400'
            else:
                out_time_str = in_time_str

            return out_time_str

        time_interval_dict = {'H': '1HOUR'}
        interv = time_interval_dict[hydrograph.index.freqstr]
        strt = hydrograph.index[0]
        end = hydrograph.index[-1]

        strtdt_frmt = strt.strftime("%d%b%Y").upper()
        strttim_frmt = strt.strftime("%H%M")
        strttim_frmt = tm_replace(strttim_frmt)
        enddt_frmt = end.strftime("%d%b%Y").upper()
        endtim_frmt = end.strftime("%H%M")
        endtim_frmt = tm_replace(endtim_frmt)

        sim_dat_strs = [strtdt_frmt, strttim_frmt, enddt_frmt, endtim_frmt]

        self._param_dict['Simulation Date'] = ','.join(sim_dat_strs)
        self._param_dict['Instantaneous Interval'] = interv

        for i, line in enumerate(self._lines):
            if 'Simulation Date' in line:
                self._lines[i] = '{0}={1}\n'.format('Simulation Date', self._param_dict['Simulation Date'])
            elif 'Instantaneous Interval' in line:
                self._lines[i] = '{0}={1}\n'.format('Instantaneous Interval',
                                                    self._param_dict['Instantaneous Interval'])
            else:
                pass

        updt_txt = ''.join(self._lines)
        with open(self.planfile, 'r+') as f:
            f.seek(0)
            f.write(updt_txt)
            f.truncate()
