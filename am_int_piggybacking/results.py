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
EXECUTION_TIME_IN_SECONDS = 1200

LABEL_DICT = {
    "am": "Active Monitoring",
    "int": "In-Band Network",
    "pb": "Piggybacking"
}

SELF_PATH = os.path.dirname(os.path.abspath(__file__))
DIAGRAMS_PATH = os.path.join(os.path.dirname(SELF_PATH), 'network')

SUBPLOT_LEFT = 0.1
SUBPLOT_BOTTOM = 0.1
SUBPLOT_WIDTH = 0.75
SUBPLOT_HEIGHT = 0.8

SUBPLOT_IMAGE_POSX = 810
SUBPLOT_IMAGE_POSY = 70
SUBPLOT_IMAGE_POSY_MULT = 60

def time_to_seconds(time_str):
    minutes, seconds = map(float, time_str.split(':'))
    total_seconds = minutes * 60 + seconds
    return total_seconds

def file_parser(folder_path, filename):
    node_ticks = {}
    node_total_ticks = {}
    bytes_per_node = {}
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
                    tm_bytes = int(match.group(1))
                    total_telemetry_bytes += tm_bytes

                    pattern = re.escape("Bytes of telemetry ") + r'(.*?)' + re.escape("\n")
                    match = re.search(pattern, line)
                    tm_source_node = match.group(1)
                    source_node = int(tm_source_node[0])
                    bytes_per_node[source_node] = bytes_per_node.get(source_node, 0)
                    bytes_per_node[source_node] += tm_bytes



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
    bytes_per_node[1] = 0
    data_object['bytes_per_node'] = bytes_per_node

    for i in range(1, data_object['number_nodes']):
        if i not in list(data_object['bytes_per_node'].keys()):
            data_object['bytes_per_node'][i] = 0

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
        plot_dict[plot_id]['nodes'] = file_data['number_nodes']
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
        fig = plt.figure(figsize=(7.4, 4.8))

        ax = fig.add_subplot(111, position=[SUBPLOT_LEFT, SUBPLOT_BOTTOM, SUBPLOT_WIDTH, SUBPLOT_HEIGHT])
        plt.title(str(plot_data['hops'] + 2) + ' nodes and ' + str(plot_data['bytes']) + ' bytes of telemetry')
        
        for type_key, type_data in plot_data['types'].items():
            y_values = []
            x_labels = []
            for node_key, node_data in type_data.items():
                y_values.append(node_data['energy_consumption'])
                x_labels.append(str(node_key))
            ax.plot(x_labels, y_values, label = LABEL_DICT[type_key])
            ax.set_xticks(x_labels)
            ax.set_ylabel('Total energy consumption in mJ')
            ax.set_xlabel('Node #')
            ax.legend()
        
        img = plt.imread(os.path.join(DIAGRAMS_PATH, str(plot_data['nodes']) + 'nodes.png'))
        fig.figimage(img, SUBPLOT_IMAGE_POSX, SUBPLOT_IMAGE_POSY + SUBPLOT_IMAGE_POSY_MULT*(7 - plot_data['nodes']))
        ax.grid()
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

def plot_bytes_per_hop(data_structure):
    plot_dict = {}
    for file_key, file_data in data_structure.items():
        plot_id = str(file_data['hops']) + '_' + str(file_data['bytes'])
        plot_dict[plot_id] = plot_dict.get(plot_id, {'hops': file_data['hops'], 'bytes': file_data['bytes']})
        plot_dict[plot_id]['nodes'] = file_data['number_nodes']
        sort_vector = []

        for i in range(plot_dict[plot_id]['hops'] + 1):
            if i >= 2:
                sort_vector.append(i + 2)
            else:
                sort_vector.append(i + 1)

        sort_vector.append(3)

        file_type = str(file_data['type'])
        plot_dict[plot_id]['types'] = plot_dict[plot_id].get('types', {})
        plot_dict[plot_id]['types'][file_type] = plot_dict[plot_id]['types'].get(file_type, file_data['bytes_per_node'])
        plot_dict[plot_id]['types'][file_type] = {k : plot_dict[plot_id]['types'][file_type][k] for k in sorted(plot_dict[plot_id]['types'][file_type], key = lambda k: sort_vector.index(k))}
    
    for plot_key, plot_data in plot_dict.items():
        fig = plt.figure(figsize=(7.4, 4.8))

        ax = fig.add_subplot(111, position=[SUBPLOT_LEFT, SUBPLOT_BOTTOM, SUBPLOT_WIDTH, SUBPLOT_HEIGHT])

        plt.title(str(plot_data['hops'] + 2) + ' nodes and ' + str(plot_data['bytes']) + ' bytes of telemetry')
        for type_key, type_data in plot_data['types'].items():
            y_values = []
            x_labels = []
            for node_key, node_data in type_data.items():
                y_values.append(node_data)
                x_labels.append(str(node_key))
            ax.plot(x_labels, y_values, label = LABEL_DICT[type_key])
            ax.set_xticks(x_labels)
            ax.set_ylabel('Total bytes of telemetry appended')
            ax.set_xlabel('Node #')
            ax.legend()
        
        img = plt.imread(os.path.join(DIAGRAMS_PATH, str(plot_data['nodes']) + 'nodes.png'))
        fig.figimage(img, SUBPLOT_IMAGE_POSX, SUBPLOT_IMAGE_POSY + SUBPLOT_IMAGE_POSY_MULT*(7 - plot_data['nodes']))
        ax.grid()
        plt.show(block = False)

def plot_average_energy_per_byte_vs_hops(data_structure):
    plot_dict = {}

    for file_key, file_data in data_structure.items():
        plot_id = str(file_data['hops']) + '_' + str(file_data['bytes'])
        plot_dict[plot_id] = plot_dict.get(plot_id, {'hops': file_data['hops'], 'bytes': file_data['bytes']})

        file_type = str(file_data['type'])
        plot_dict[plot_id]['types'] = plot_dict[plot_id].get('types', {})
        plot_dict[plot_id]['types'][file_type] = plot_dict[plot_id]['types'].get(file_type, 0)
        plot_dict[plot_id]['types'][file_type]= file_data['total_energy_consumption'] / file_data['telemetry_bytes_transmited']
    
    for plot_key, plot_data in plot_dict.items():
        plt.figure()
        plt.title(str(plot_data['hops'] + 2) + ' nodes and ' + str(plot_data['bytes']) + ' bytes of telemetry')
        x_values = list(plot_data['types'].keys())
        y_values = []
        for types_key, types_data in plot_data['types'].items():
            y_values.append(types_data)
        
        for i in range(len(x_values)):
            x_values[i] = LABEL_DICT[x_values[i]]
        plt.xlabel('Method')
        plt.ylabel('mJ / Byte of telemetry transmitted')
        plt.bar(x_values, y_values, color ='maroon', width = 0.4)
        plt.show(block = False)

def plot_byte_cost_vs_nodes_legend_type_bytes_windows(data_structure):
    plot_dict = {}

    for file_key, file_data in data_structure.items():
        plot_id = str(file_data['bytes'])
        plot_dict[plot_id] = plot_dict.get(plot_id, {})
        plot_dict[plot_id]['number_nodes_unique'] = plot_dict[plot_id].get('number_nodes_unique', set())
        plot_dict[plot_id]['number_nodes_ordered'] = plot_dict[plot_id].get('number_nodes_ordered', [])

        if str(file_data['number_nodes']) not in plot_dict[plot_id]['number_nodes_unique']:
            plot_dict[plot_id]['number_nodes_unique'].add(str(file_data['number_nodes']))
            plot_dict[plot_id]['number_nodes_ordered'].append(str(file_data['number_nodes']) + ' Nodes')

        plot_dict[plot_id]['measurements'] = plot_dict[plot_id].get('measurements', {})

        type = str(file_data['type'])
        plot_dict[plot_id]['measurements'][type] = plot_dict[plot_id]['measurements'].get(type, [])
        plot_dict[plot_id]['measurements'][type].append(file_data['total_energy_consumption'] / file_data['telemetry_bytes_transmited'])

    
    for plot_key, plot_data in plot_dict.items():  
        nodes = list(plot_data['number_nodes_ordered'])
        x = np.arange(len(nodes))  # the label locations
        width = 0.25  # the width of the bars
        multiplier = 0

        averages = {key: sum(values) / len(values) for key, values in plot_data['measurements'].items()}
        sorted_keys = sorted(plot_data['measurements'].keys(), key=lambda x: averages[x])
        sorted_measurements = {key: plot_data['measurements'][key] for key in sorted_keys}

        fig, ax = plt.subplots(layout = 'constrained')
        for attr, measurement in sorted_measurements.items():
            offset = width * multiplier
            rects = ax.bar(x + offset, measurement, width, label=LABEL_DICT[attr])
            ax.bar_label(rects, padding=2, fmt='{:.2f}')
            multiplier += 1

        
        ax.set_ylabel('Byte cost (mJ/byte)')
        ax.set_title('Byte cost per method')
        ax.set_xticks(x + width, plot_data['number_nodes_ordered'])
        ax.legend(loc='upper left', ncols=3)
        ax.set_ylim(0, 1.6)

        plt.show(block = False)

def main():
    FOLDER_PATH = os.path.join(SELF_PATH, "datafiles")
    file_cnt = 0
    data = {}
    for filename in os.listdir(FOLDER_PATH):
        data['file' + str(file_cnt)] = file_parser(FOLDER_PATH, filename)
        file_cnt += 1
    
    # plot_total_energy_vs_hops_allnodes(data)
    plot_energy_per_hop(data)
    # plot_energy_vs_hops_legend_bytes_types_windows(data)  
    # plot_energy_vs_nodes_legend_type_bytes_windows(data)
    # plot_bytes_per_hop(data)
    # plot_average_energy_per_byte_vs_hops(data)
    # plot_byte_cost_vs_nodes_legend_type_bytes_windows(data)
    plt.show()




if __name__ == "__main__":
    main()
