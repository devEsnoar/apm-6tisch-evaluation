import os
import re
import numpy as np
import matplotlib.pyplot as plt

DATA = {}

CURRENT_MA = {
    "Radio Rx" : 18.8,
    "Radio Tx" : 17.4,
}

STATES = list(CURRENT_MA.keys())

RTIMER_ARCH_SECOND = 1000000 # Cooja RTIMER_ARCH_SECOND
VOLTAGE = 3.0 # assume 3 volt batteries
EXECUTION_TIME_IN_SECONDS = 600

LABEL_DICT = {
    "am": "Active Monitoring",
    "int": "In-Band Network"
}

SELF_PATH = os.path.dirname(os.path.abspath(__file__))


def time_to_seconds(time_str):
    minutes, seconds = map(float, time_str.split(':'))
    total_seconds = minutes * 60 + seconds
    return total_seconds

def file_parser(folder_path, filename):
    node_ticks = {}
    node_total_ticks = {}
    total_telemetry_bytes = 0
    t_zero = -1
    t_sim = 0

    INPUT_FILE = os.path.join(folder_path, filename)
    with open(INPUT_FILE, "r") as f:
        print(filename)
        for line in f:
            if not t_zero > 0:
                if "ID:3\t### Joined the network ###" not in line:
                    continue

                fields = line.split()
                try:
                    t_zero = time_to_seconds(fields[0])
                except:
                    continue
            else:
                if re.search(r'ID:1(.*)EXPERIMENT: Consumed', line):
                    pattern = re.escape("Consumed ") + r'(.*?)' + re.escape(" Bytes")
                    match = re.search(pattern, line)
                    total_telemetry_bytes += int(match.group(1))

                if t_sim > EXECUTION_TIME_IN_SECONDS:
                    break

                if "INFO: Energest" not in line:
                    continue

                if "Period summary" in line:
                    continue


                fields = line.split()
                # print(fields)
                try:
                    node_field = fields[1].split(':')
                    node = int(node_field[1])
                except:
                    continue
                    
                if node not in node_ticks:
                    node_ticks[node] = { u : 0  for u in STATES }
                    node_total_ticks[node] = 0
                
                try:
                    state_index = 5
                    state = fields[state_index]
                    tick_index = state_index + 2
                    if state not in STATES:
                        state = fields[state_index] + " " + fields[state_index+1]
                        tick_index += 1
                        if state not in STATES:
                            # add to the total time
                            if state == "Total time":
                                node_total_ticks[node] += int(fields[tick_index])
                            continue
                    # add to the time spent in specific state
                    ticks = int(fields[tick_index][:-1])
                    node_ticks[node][state] += ticks
                    t_sim = time_to_seconds(fields[0]) - t_zero
                except Exception as ex:
                    print("Failed to process line '{}': {}".format(line, ex))
    
    nodes = sorted(node_ticks.keys())

    filename_fields = filename.split('_')
    data_object = {}
    data_object['type'] = filename_fields[0]
    data_object['hops'] = int(filename_fields[1])
    data_object['bytes'] = int(filename_fields[3])
    data_object['number_nodes'] = data_object['hops'] + 2
    data_object['nodes'] = { i + 1 : 0 for i in range(data_object['number_nodes'])}
    data_object['total_energy_consumption'] = 0

    for node in nodes:
        
        total_avg_current_mA = 0
        period_ticks = node_total_ticks[node]
        period_seconds = period_ticks / RTIMER_ARCH_SECOND
        for state in STATES:
            ticks = node_ticks[node].get(state, 0)
            current_mA = CURRENT_MA[state]
            state_avg_current_mA = ticks * current_mA / period_ticks
            total_avg_current_mA += state_avg_current_mA
        total_charge_mC = period_ticks * total_avg_current_mA / RTIMER_ARCH_SECOND
        total_energy_mJ = total_charge_mC * VOLTAGE
        
        data_object['nodes'][node] = {
            'energy_consumption': total_energy_mJ,
            'total_charge': total_charge_mC,
            'period_seconds': period_seconds
        }

        data_object['total_energy_consumption'] += total_energy_mJ

        print("Node {}: {:.2f} mC ({:.3f} mAh) charge consumption, {:.2f} mJ energy consumption in {:.2f} seconds".format(
            node, total_charge_mC, total_charge_mC / 3600.0, total_energy_mJ, period_seconds))
    print("Total telemetry bytes transmitted: {}".format(total_telemetry_bytes))

    data_object['sim_time'] = t_sim
    data_object['telemetry_bytes_transmited'] = total_telemetry_bytes
    return data_object


def plot_total_energy_vs_hops_allnodes(data_structure):
    energy = {}
    hops = {}

    for file in data_structure:
        file_type = str(data_structure[file]['type'])
        energy[file_type] = energy.get(file_type, [])
        hops[file_type] = hops.get(file_type, [])
        energy[file_type].append(data_structure[file]['total_energy_consumption'])
        hops[file_type].append(str(data_structure[file]['hops']))
    
    types = list(energy.keys())
    format = ['ro', 'bs']
    cnt = 0
    for type in types:
        plt.plot(hops[type], energy[type], format[cnt], label = LABEL_DICT[type])
        cnt += 1

    plt.ylabel('Total energy consumption in mJ')
    plt.xlabel('Number of nodes')
    plt.legend()
    plt.show(block = False)

def plot_energy_per_hop(data_structure):

    plot_dict = {}

    for file_key, file_data in data_structure.items():
        plot_id = str(file_data['hops']) + '_' + str(file_data['bytes'])
        plot_dict[plot_id] = plot_dict.get(plot_id, {'hops': file_data['hops'], 'bytes': file_data['bytes']})
        sort_vector = []

        for i in range(plot_dict[plot_id]['hops'] + 1):
            if i >= 2:
                sort_vector.append(i + 2)
            else:
                sort_vector.append(i + 1)
        
        sort_vector.append(3)

        file_type = str(file_data['type'])
        plot_dict[plot_id]['types'] = plot_dict[plot_id].get('types', {})
        plot_dict[plot_id]['types'][file_type] = plot_dict[plot_id]['types'].get(file_type, file_data['nodes'])
        plot_dict[plot_id]['types'][file_type] = {k : plot_dict[plot_id]['types'][file_type][k] for k in sorted(plot_dict[plot_id]['types'][file_type], key = lambda k: sort_vector.index(k))}

    for plot_key, plot_data in plot_dict.items():
        plt.figure()
        plt.title(str(plot_data['hops'] + 2) + ' nodes and ' + str(plot_data['bytes']) + ' bytes of telemetry')
        for type_key, type_data in plot_data['types'].items():
            y_values = []
            x_labels = []
            for node_key, node_data in type_data.items():
                y_values.append(node_data['energy_consumption'])
                x_labels.append(str(node_key))
            plt.plot(x_labels, y_values, label = LABEL_DICT[type_key])
            plt.xticks(x_labels)
            plt.ylabel('Total energy consumption in mJ')
            plt.xlabel('Node #')
            plt.legend()
            
        plt.grid()
        plt.show(block = False)

def plot_energy_vs_hops_legend_bytes_types_windows(data_structure):

    plot_dict = {}

    for file_key, file_data in data_structure.items():
        plot_id = file_data['type']
        plot_dict[plot_id] = plot_dict.get(plot_id, {})
        plot_dict[plot_id][str(file_data['bytes'])] = plot_dict[plot_id].get(str(file_data['bytes']), {'hops': [], 'total_energy': []})
        plot_dict[plot_id][str(file_data['bytes'])]['hops'].append(str(file_data['hops']))
        plot_dict[plot_id][str(file_data['bytes'])]['total_energy'].append(file_data['total_energy_consumption'])
    
    for plot_key, plot_data in plot_dict.items():
        plt.figure()
        plt.title(LABEL_DICT[plot_key] + ': Energy consumption vs hops vs bytes')
        plt.grid()
        for byte_key, byte_data in plot_data.items():
            x_values = byte_data['hops']
            y_values = byte_data['total_energy']
            plt.plot(x_values, y_values, label = byte_key + ' Bytes')
            plt.xticks(x_values)
            plt.ylabel('Total energy consumption in mJ')
            plt.xlabel('# of Hops')
            plt.legend()
            plt.show(block = False)


def plot_energy_vs_nodes_legend_type_bytes_windows(data_structure):
    
    plot_dict = {}

    for file_key, file_data in data_structure.items():
        plot_id = str(file_data['bytes'])
        plot_dict[plot_id] = plot_dict.get(plot_id, {})
        plot_dict[plot_id][str(file_data['type'])] = plot_dict[plot_id].get(str(file_data['type']), {'nodes': [], 'total_energy': []})
        plot_dict[plot_id][str(file_data['type'])]['nodes'].append(str(file_data['number_nodes']))
        plot_dict[plot_id][str(file_data['type'])]['total_energy'].append(file_data['total_energy_consumption'])

    for plot_key, plot_data in plot_dict.items():
        plt.figure()
        plt.title(plot_key + ' Bytes: Energy consumption vs nodes vs type')
        plt.grid()
        for type_key, type_data in plot_data.items():
            x_values = type_data['nodes']
            y_values = type_data['total_energy']
            plt.plot(x_values, y_values, label = LABEL_DICT[type_key])
            plt.xticks(x_values)
            plt.ylabel('Total energy consumption in mJ')
            plt.xlabel('# nodes')
            plt.legend()
            plt.show(block = False)

def main():
    FOLDER_PATH = os.path.join(SELF_PATH, "datafiles")
    file_cnt = 0
    data = {}
    for filename in os.listdir(FOLDER_PATH):
        data['file' + str(file_cnt)] = file_parser(FOLDER_PATH, filename)
        file_cnt += 1
    
    # plot_total_energy_vs_hops_allnodes(data)
    # plot_energy_per_hop(data)
    plot_energy_vs_hops_legend_bytes_types_windows(data)
    # plot_energy_vs_nodes_legend_type_bytes_windows(data)

    plt.show()




if __name__ == "__main__":
    main()
