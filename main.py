import time
from operator import attrgetter
import numpy as np
import struct as st

DATA = "sim_data"
max_c = 341  # 25 * 7   # 最大桶容量 10<c<1000 c=70效果最好 7 70 700
flag = 0    # 表示分裂次数，用来循环分裂操作flag % 3 == 0时分裂x；flag % 3 == 1时分裂y；flag % 3 == 2时分裂z
if DATA == "sim_data":
    data_file_name = "sim.dat"
    index_file_name = "sim.idx"
    range_query_file_name = "rangeQuery_sim.txt"
    point_query_file1_name = "pointQuery1_sim.txt"
    point_query_file2_name = "pointQuery2_sim.txt"
    nx = 30      #
    ny = 30      #
    nz = 30      # grid array 大小
    max_x_value = 50000     # x
    min_x_value = 0
    max_y_value = 50000     # y
    min_y_value = 0
    max_z_value = 1000      # t
    min_z_value = 0
    max_count = 300000  # 一期20w数据
    ep_time = 1000
elif DATA == "geo_data":
    data_file_name = "geo.dat"
    index_file_name = "geo.idx"
    range_query_file_name = "rangeQuery_real.txt"
    point_query_file_name = "pointQuery_real.txt"
    nx = 5      #
    ny = 5      #
    nz = 110      # grid array 大小
    max_x_value = 116.7285615      # x
    max_y_value = 40.1799936     # y
    min_x_value = 116.0800006   # 116.0800006
    min_y_value = 39.6800104000001     # 39.6800104000001
    max_z_value = 90000      # t
    min_z_value = 0
    max_count = 200000  # 一期20w数据


class Record:
    x = 0.0
    y = 0.0
    z = 0.0


class Position:
    x = 0
    y = 0
    z = 0


class Range:
    x_min = 0.0
    x_max = 0.0
    y_min = 0.0
    y_max = 0.0
    z_min = 0.0
    z_max = 0.0


# 块类
class Block:
    id = 0
    list = []


# 缓存区类
class Buffer:
    id_list = []  # 用于存放块号，用于先进先出
    block_dict = {}  # 块号：块
    max_size = 0

    # 将块添加入缓存区
    def append(self, block):
        if len(self.id_list) < self.max_size:
            self.id_list.append(block.id)
            self.block_dict[block.id] = block
        else:
            out_block_id = self.id_list[0]
            del self.id_list[0]
            del self.block_dict[out_block_id]
            self.id_list.append(block.id)
            self.block_dict[block.id] = block


# 写数据块（块）
def write_block(block):
    data_file.seek(block.id * (max_c * 24 + 8))  # 每个桶存max_c*24B的数据，即max_c个点
    for record in block.list:
        b_x = st.pack("d", record.x)
        b_y = st.pack("d", record.y)
        b_z = st.pack("d", record.z)
        data_file.write(b_x)
        data_file.write(b_y)
        data_file.write(b_z)
    for i in range(max_c - len(block.list)):
        data_file.write(st.pack("d", 0))
        data_file.write(st.pack("d", 0))
        data_file.write(st.pack("d", 0))
    data_file.write(st.pack("d", 0))


# 建立模型
# 建立3维栅格数组
# 3维栅格数组，数组值为桶号，初始为桶0
grid_array = np.arange(nx * ny * nz).reshape(nx, ny, nz)
# 建立线性刻度，方便查找
X = [min_x_value]  # 线性刻度
Y = [min_y_value]
Z = [min_z_value]
# 建立B数组，用来装桶
B = []
num = 0
for i in range(nx):
    for j in range(ny):
        for k in range(nz):
            bucket = Block()
            bucket.id = num
            num += 1
            bucket.list = []
            B.append(bucket)


# Split
# 按x坐标分割，竖着切一刀
# k表示现在桶id
def split_x(pos):
    global num
    global nx
    global grid_array
    old_bucket_id = grid_array[pos.x][pos.y][pos.z]
    mid_x = (X[pos.x] + X[pos.x + 1]) / 2
    X.insert(pos.x + 1, mid_x)
    nx += 1
    # 给新分割的栅格块分配新桶
    # grid array切割
    grid_array = np.insert(grid_array, pos.x, grid_array[pos.x], axis=0)
    grid_array[pos.x + 1][pos.y][pos.z] = num
    # 将bucket中大于x_mid对应的线性刻度的记录移到bucket_new中
    y_min = Y[pos.y]
    y_max = Y[pos.y + 1]
    z_min = Z[pos.z]
    z_max = Z[pos.z + 1]
    # 添加新桶
    new_bucket = Block()
    new_bucket.id = num
    new_bucket.list = []
    num += 1
    B.append(new_bucket)
    remove_record = []
    for record in B[old_bucket_id].list:
        if X[pos.x] <= record.x < mid_x and y_min <= record.y < y_max and z_min <= record.z % ep_time < z_max:  # 如果小于，则写入新桶，并删除
            B[new_bucket.id].list.append(record)
            remove_record.append(record)
    for record in remove_record:
        B[old_bucket_id].list.remove(record)


# 按y坐标分割，竖着切一刀
# k表示现在桶id
def split_y(pos):
    global num
    global ny
    global grid_array
    old_bucket_id = grid_array[pos.x][pos.y][pos.z]
    mid_y = (Y[pos.y] + Y[pos.y + 1]) / 2
    Y.insert(pos.y + 1, mid_y)
    ny += 1
    # 给新分割的栅格块分配新桶
    # grid array切割
    grid_array = np.insert(grid_array, pos.y, grid_array[:, pos.y], axis=1)
    grid_array[pos.x][pos.y + 1][pos.z] = num
    # 将bucket中大于x_mid对应的线性刻度的记录移到bucket_new中
    x_min = X[pos.x]
    x_max = X[pos.x + 1]
    z_min = Z[pos.z]
    z_max = Z[pos.z + 1]
    # 添加新桶
    new_bucket = Block()
    new_bucket.id = num
    new_bucket.list = []
    num += 1
    B.append(new_bucket)
    remove_record = []
    for record in B[old_bucket_id].list:
        if x_min <= record.x < x_max and Y[pos.y] <= record.y < mid_y and z_min <= record.z % ep_time < z_max:  # 如果小于，则写入新桶，并删除
            B[new_bucket.id].list.append(record)
            remove_record.append(record)
    for record in remove_record:
        B[old_bucket_id].list.remove(record)


# 按z坐标分割，竖着切一刀
# k表示现在桶id
def split_z(pos):
    global num
    global nz
    global grid_array
    old_bucket_id = grid_array[pos.x][pos.y][pos.z]
    mid_z = (Z[pos.z] + Z[pos.z + 1]) / 2
    Z.insert(pos.z + 1, mid_z)
    nz += 1
    # 给新分割的栅格块分配新桶
    # grid array切割
    grid_array = np.insert(grid_array, pos.z, grid_array[:, :, pos.z], axis=2)
    grid_array[pos.x][pos.y][pos.z + 1] = num
    # 将bucket中大于x_mid对应的线性刻度的记录移到bucket_new中
    x_min = X[pos.x]
    x_max = X[pos.x + 1]
    y_min = Y[pos.z]
    y_max = Y[pos.z + 1]
    # 添加新桶
    new_bucket = Block()
    new_bucket.id = num
    new_bucket.list = []
    num += 1
    B.append(new_bucket)
    remove_record = []
    for record in B[old_bucket_id].list:
        if x_min <= record.x < x_max and y_min <= record.y < y_max and Z[pos.z] <= record.z % ep_time < mid_z:  # 如果小于，则写入新桶，并删除
            B[new_bucket.id].list.append(record)
            remove_record.append(record)
    for record in remove_record:
        B[old_bucket_id].list.remove(record)


# 在线性刻度上查找记录，返回grid_array中的三维坐标
def find(r):
    pos = Position()
    for i in range(nx):
        if r.x < X[i]:
            pos.x = i - 1
            break
    for i in range(ny):
        if r.y < Y[i]:
            pos.y = i - 1
            break
    for i in range(nz):
        if r.z < Z[i]:
            pos.z = i - 1
            break
    return pos


# 将记录r插入栅格文件中
def insert(r):
    global flag     # 声明使用全局变量flag
    global count
    global ep
    global num
    global data_buffer
    global index_buffer
    global visit_time
    pos = find(r)
    if ep == 1:
        bucket_id = grid_array[pos.x][pos.y][pos.z]
        B[bucket_id].list.append(r)
        if len(B[bucket_id].list) > max_c:
            flag += 1
    elif ep > 1:
        # 插入时，要加上周期时间 ep=1 0~1000
        r.z = r.z + (ep - 1) * ep_time
        # 根据栅格数组的值，找到桶
        # 根据grid array中的位置，计算出索引块号以及块中位置
        block_id = int((pos.x * ny * nz + pos.y * nz + pos.z) / 1024)
        pos_in_block = pos.x * ny * nz + pos.y * nz + pos.z - block_id * 1024
        # 现在缓冲区中查找索引块
        find_block = 0
        if len(index_buffer.id_list) != 0 and block_id in index_buffer.block_dict:
            block = index_buffer.block_dict[block_id]
            # bucket_id = block.list[pos_in_block]
            find_block = 1
        # 如果缓冲区中没找到，则去硬盘读取索引块
        if find_block == 0:
            with open(index_file_name, 'rb') as index_file:
                visit_time += 1
                index_file.seek(block_id * 8 * 1024)
                index_str = index_file.read(8 * 1024)
                index_block = Block()
                index_block.id = block_id
                index_block.list = []
                for i in range(1024):
                    if len(index_str[i * 8:i * 8 + 8]) != 8:
                        break
                    index_tuple = st.unpack("q", index_str[i * 8:i * 8 + 8])
                    index_block.list.append(index_tuple[0])
                # bucket_id = index_block.list[pos_in_block]
                index_buffer.append(index_block)
        bucket_id = grid_array[pos.x][pos.y][pos.z]
        # 将记录r插入桶
        # 在缓存中寻找数据块，如果找到直接在缓存中的数据块中查找点
        find_block = 0
        if len(data_buffer.id_list) != 0 and bucket_id in data_buffer.block_dict:
            bucket = data_buffer.block_dict[bucket_id]
            bucket.list.append(r)
            B[bucket_id].list.append(r)
            find_block = 1
        # 在缓存中没找到数据块，则到硬盘上找，并加入缓存中，然后查找点
        if find_block == 0:
            with open(data_file_name, 'rb') as data_file:
                visit_time += 1
                data_file.seek(bucket_id * (max_c * 24 + 8))
                str = data_file.read(max_c * 24 + 8)
                bucket = Block()
                bucket.id = bucket_id
                bucket.list = []
                for i in range(max_c):
                    if len(str[i * 24:i * 24 + 24]) != 24:
                        break
                    record_str = st.unpack('ddd', str[i * 24:i * 24 + 24])
                    if record_str[0] == 0 and record_str[1] == 0 and record_str[2] == 0:
                        break
                    record = Record()
                    record.x = record_str[0]
                    record.y = record_str[1]
                    record.z = record_str[2]
                    bucket.list.append(record)
                bucket.list.append(r)
            B[bucket_id].list.append(r)
            # 如果桶溢出,则进行分裂操作
            # 分裂前检查是否两个块指向一个桶！！！
            if len(B[bucket_id].list) > max_c:
                if grid_array[pos.x + 1][pos.y][pos.z] == bucket_id:
                    remove_record = []
                    new_bucket = Block()
                    new_bucket.list = []
                    new_bucket.id = num
                    num += 1
                    grid_array[pos.x + 1][pos.y][pos.z] = new_bucket.id
                    for record in B[bucket_id].list:
                        if record.x >= X[pos.x + 1]:    # 如果大于，则写入新桶，并删除
                            new_bucket.list.append(record)
                            remove_record.append(record)
                    for record in remove_record:
                        B[bucket_id].list.remove(record)
                    B.append(new_bucket)
                elif grid_array[pos.x - 1][pos.y][pos.z] == bucket_id:
                    remove_record = []
                    new_bucket = Block()
                    new_bucket.list = []
                    new_bucket.id = num
                    num += 1
                    grid_array[pos.x - 1][pos.y][pos.z] = new_bucket.id
                    for record in B[bucket_id].list:
                        if record.x < X[pos.x]:  # 如果小于，则写入新桶，并删除
                            new_bucket.list.append(record)
                            remove_record.append(record)
                    for record in remove_record:
                        B[bucket_id].list.remove(record)
                    B.append(new_bucket)
                elif grid_array[pos.x][pos.y + 1][pos.z] == bucket_id:
                    remove_record = []
                    new_bucket = Block()
                    new_bucket.list = []
                    new_bucket.id = num
                    num += 1
                    grid_array[pos.x][pos.y + 1][pos.z] = new_bucket.id
                    for record in B[bucket_id].list:
                        if record.y >= Y[pos.y + 1]:  # 如果大于，则写入新桶，并删除
                            new_bucket.list.append(record)
                            remove_record.append(record)
                    for record in remove_record:
                        B[bucket_id].list.remove(record)
                    B.append(new_bucket)
                elif grid_array[pos.x][pos.y - 1][pos.z] == bucket_id:
                    remove_record = []
                    new_bucket = Block()
                    new_bucket.list = []
                    new_bucket.id = num
                    num += 1
                    grid_array[pos.x][pos.y - 1][pos.z] = new_bucket.id
                    for record in B[bucket_id].list:
                        if record.y < Y[pos.y]:  # 如果小于，则写入新桶，并删除
                            new_bucket.list.append(record)
                            remove_record.append(record)
                    for record in remove_record:
                        B[bucket_id].list.remove(record)
                    B.append(new_bucket)
                elif grid_array[pos.x][pos.y][pos.z + 1] == bucket_id:
                    remove_record = []
                    new_bucket = Block()
                    new_bucket.list = []
                    new_bucket.id = num
                    num += 1
                    grid_array[pos.x][pos.y][pos.z + 1] = new_bucket.id
                    for record in B[bucket_id].list:
                        if record.z % ep_time >= Z[pos.z + 1]:  # 如果大于，则写入新桶，并删除
                            new_bucket.list.append(record)
                            remove_record.append(record)
                    for record in remove_record:
                        B[bucket_id].list.remove(record)
                    B.append(new_bucket)
                elif grid_array[pos.x][pos.y][pos.z - 1] == bucket_id:
                    remove_record = []
                    new_bucket = Block()
                    new_bucket.list = []
                    new_bucket.id = num
                    num += 1
                    grid_array[pos.x][pos.y][pos.z - 1] = new_bucket.id
                    for record in B[bucket_id].list:
                        if record.z % ep_time < Z[pos.z]:  # 如果小于，则写入新桶，并删除
                            new_bucket.list.append(record)
                            remove_record.append(record)
                    for record in remove_record:
                        B[bucket_id].list.remove(record)
                    B.append(new_bucket)
                # 设置一个flag 划分一次变一个值，循环划分，偶数横向划分，奇数纵向划分
                elif flag % 3 == 0:
                    split_x(pos)
                    flag += 1
                elif flag % 3 == 1:
                    split_y(pos)
                    flag += 1
                elif flag % 3 == 2:
                    split_z(pos)
                    flag += 1
            data_buffer.append(bucket)


def point_query(r):
    global visit_time
    global index_buffer
    global data_buffer
    global nx, ny, nz
    # 根据linear scale找到grid array中的位置
    ep = int(r.z / ep_time) + 1
    r.z = r.z % ep_time
    pos = find(r)
    # 根据grid array中的位置，计算出索引块号以及块中位置
    block_id = int((pos.x * ny * nz + pos.y * nz + pos.z) / 1024)
    pos_in_block = pos.x * ny * nz + pos.y * nz + pos.z - block_id * 1024
    # 现在缓冲区中查找索引块
    find_block = 0
    if len(index_buffer.id_list) != 0 and block_id in index_buffer.block_dict:
        block = index_buffer.block_dict[block_id]
        bucket_id = block.list[pos_in_block]
        find_block = 1
    # 如果缓冲区中没找到，则去硬盘读取索引块
    if find_block == 0:
        with open(index_file_name, 'rb') as index_file:
            visit_time += 1
            index_file.seek(block_id * 8 * 1024)
            index_str = index_file.read(8 * 1024)
            index_block = Block()
            index_block.id = block_id
            index_block.list = []
            for i in range(1024):
                if len(index_str[i * 8:i * 8 + 8]) != 8:
                    break
                index_tuple = st.unpack("q", index_str[i*8:i*8+8])
                index_block.list.append(index_tuple[0])
            bucket_id = index_block.list[pos_in_block]
            index_buffer.append(index_block)
    # 在缓存中寻找数据块，如果找到直接在缓存中的数据块中查找点
    if len(data_buffer.id_list) != 0 and bucket_id in data_buffer.block_dict:
        bucket = data_buffer.block_dict[bucket_id]
        for record in bucket.list:
            if record.x == r.x and record.y == r.y and record.z == r.z + (ep - 1) * ep_time:
                return 1
        return 0
    # 在缓存中没找到数据块，则到硬盘上找，并加入缓存中，然后查找点
    with open(data_file_name, 'rb') as data_file:
        visit_time += 1
        data_file.seek(bucket_id * (max_c * 24 + 8))
        str = data_file.read(max_c * 24 + 8)
        bucket = Block()
        bucket.id = bucket_id
        bucket.list = []
        for i in range(max_c):
            if len(str[i * 24:i * 24 + 24]) != 24:
                break
            record_str = st.unpack('ddd', str[i*24:i*24+24])
            if record_str[0] == 0 and record_str[1] == 0 and record_str[2] == 0:
                break
            record = Record()
            record.x = record_str[0]
            record.y = record_str[1]
            record.z = record_str[2]
            bucket.list.append(record)
        data_buffer.append(bucket)
        for record in bucket.list:
            if record.x == r.x and record.y == r.y and record.z == r.z + (ep - 1) * ep_time:
                return 1
    return 0


# 范围查询函数，传入范围，输出点数组
def range_query(rang):
    global visit_time
    global index_buffer
    global data_buffer
    bucket_id_set = set()
    pos_list = []
    range_array = []
    # grid array中结束点的位置
    r = Record()
    r.x = rang.x_max
    r.y = rang.y_max
    r.z = rang.z_max
    end_pos = find(r)
    # grid array中开始点的位置
    r = Record()
    r.x = rang.x_min
    r.y = rang.y_min
    r.z = rang.z_min
    start_pos = find(r)
    # 将范围中每个点的位置存入位置数组
    for i in range(start_pos.x, end_pos.x + 1):
        for j in range(start_pos.y, end_pos.y + 1):
            for k in range(start_pos.z, end_pos.z + 1):
                pos = Position()
                pos.x = i
                pos.y = j
                pos.z = k
                pos_list.append(pos)
    # 遍历位置数组，在索引块中查找并加入桶号集合
    for pos in pos_list:
        # 根据grid array中的位置，计算出索引块号以及块中位置
        block_id = int((pos.x * ny * nz + pos.y * nz + pos.z) / 1024)
        pos_in_block = pos.x * ny * nz + pos.y * nz + pos.z - block_id * 1024
        # 现在缓冲区中查找索引块
        find_block = 0
        if len(index_buffer.id_list) != 0 and block_id in index_buffer.block_dict:
            block = index_buffer.block_dict[block_id]
            bucket_id = block.list[pos_in_block]
            find_block = 1
        # 如果缓冲区中没找到，则去硬盘读取缓存块
        if find_block == 0:
            with open(index_file_name, 'rb') as index_file:
                visit_time += 1
                index_file.seek(block_id * 8 * 1024)
                index_str = index_file.read(8 * 1024)
                index_block = Block()
                index_block.id = block_id
                index_block.list = []
                for i in range(1024):
                    if len(index_str[i * 8:i * 8 + 8]) != 8:
                        break
                    id = st.unpack("q", index_str[i*8:i*8+8])
                    index_block.list.append(id[0])
                bucket_id = index_block.list[pos_in_block]
                bucket_id_set.add(bucket_id)
                index_buffer.append(index_block)
        bucket_id_set.add(bucket_id)
    # 在桶号集合中查找，遍历每一个桶，查找范围中的点
    for bucket_id in bucket_id_set:
        # 在缓存中寻找数据块，如果找到直接在缓存中的数据块中查找点
        find_block = 0
        if len(data_buffer.id_list) != 0 and bucket_id in data_buffer.block_dict:
            find_block = 1
            bucket = data_buffer.block_dict[bucket_id]
            for record in bucket.list:
                if (rang.x_min <= record.x <= rang.x_max) and (rang.y_min <= record.y <= rang.y_max) and (
                        rang.z_min <= record.z % ep_time <= rang.z_max):
                    range_array.append(record)
        # 在缓存中没找到数据块，则到硬盘上找，并加入缓存中，然后查找点
        if find_block == 0:
            with open(data_file_name, 'rb') as data_file:
                visit_time += 1
                data_file.seek(bucket_id * (max_c * 24 + 8))
                str = data_file.read(max_c * 24 + 8)
                bucket = Block()
                bucket.id = bucket_id
                bucket.list = []
                data_buffer.append(bucket)
                for i in range(max_c):
                    record_str = st.unpack('ddd', str[i * 24:i * 24 + 24])
                    if record_str[0] == 0 and record_str[1] == 0 and record_str[2] == 0:
                        break
                    record = Record()
                    record.x = record_str[0]
                    record.y = record_str[1]
                    record.z = record_str[2]
                    bucket.list.append(record)
                    if (rang.x_min <= record.x <= rang.x_max) and (rang.y_min <= record.y <= rang.y_max) and (
                            rang.z_min <= record.z % ep_time <= rang.z_max):
                        range_array.append(record)
    return range_array


# 第一期静态装入
data_buffer = Buffer()
data_buffer.max_size = 128
data_buffer.id_list = []
data_buffer.block_dict = {}
index_buffer = Buffer()
index_buffer.max_size = 512
index_buffer.id_list = []
index_buffer.block_dict = {}
visit_time = 0
count = 0
R = []
ep = 1
print('ep' + str(ep))
time_start = time.time()
for i in range(300):
    with open(DATA + '/EP1/' + str(i) + '.txt') as file_object:
        for line in file_object:
            line = line.rstrip()
            line = line.split(",")
            r = Record()
            r.x = float(line[3])
            r.y = float(line[4])
            r.z = int(line[1])
            R.append(r)
print(len(R))
R.sort(key=attrgetter("x"))
for i in range(1, nx):
    X.append(R[i * int(max_count/nx)].x)
X.append(max_x_value)
print(X)
R.sort(key=attrgetter("y"))
for i in range(1, ny):
    Y.append(R[i * int(max_count/ny)].y)
Y.append(max_y_value)
print(Y)
R.sort(key=attrgetter("z"))
for i in range(1, nz):
    Z.append(R[i * int(max_count/nz)].z)
Z.append(max_z_value)
print(Z)
for r in R:
    insert(r)
# 将grid array 写入硬盘
index_file = open(index_file_name, 'wb')
for i in range(nx):
    for j in range(ny):
        for k in range(nz):
            bucket_id = st.pack("q", grid_array[i][j][k])
            index_file.write(bucket_id)
index_file.close()
# 将桶中数据写入硬盘
data_file = open(data_file_name, 'wb')
for i in range(num):
    write_block(B[i])
data_file.close()
time_end = time.time()
print('cost of build time:', time_end - time_start, 's')
print('flag = ' + str(flag))


# 静态装入点查询
# 一个索引块可以放1024(1000)个索引项 1000 * 8
# 一个数据块可以放341个数据
data_buffer = Buffer()
data_buffer.max_size = 128
data_buffer.id_list = []
data_buffer.block_dict = {}
index_buffer = Buffer()
index_buffer.max_size = 512
index_buffer.id_list = []
index_buffer.block_dict = {}
time_start = time.time()
success = 0
fail = 0
visit_time = 0
index_file = open(index_file_name, "rb")
data_file = open(data_file_name, "rb")
with open(point_query_file1_name) as file_object:
    for line in file_object:
        line = line.rstrip()
        line = line.split(",")
        r = Record()
        r.x = float(line[0])
        r.y = float(line[1])
        r.z = float(line[2])
        result = point_query(r)
        if result == 1:
            success += 1
        elif result == 0:
            fail += 1
time_end = time.time()
print('point_query_time cost:', time_end - time_start, 's')
print('visit time:', visit_time)


# 范围查询
data_buffer = Buffer()
data_buffer.max_size = 128
data_buffer.id_list = []
data_buffer.block_dict = {}
index_buffer = Buffer()
index_buffer.max_size = 512
index_buffer.id_list = []
index_buffer.block_dict = {}
record_sum = 0
visit_time = 0
time_start = time.time()
# 将索引块加入缓存区
index_file = open(index_file_name, "rb")
data_file = open(data_file_name, "rb")
with open(range_query_file_name) as file_object:
    for line in file_object:
        line = line.rstrip()
        line = line.split(",")
        rang = Range()
        rang.x_min = float(line[0])
        rang.x_max = float(line[1])
        rang.y_min = float(line[2])
        rang.y_max = float(line[3])
        rang.z_min = float(line[4])
        rang.z_max = float(line[5])
        if rang.z_max > ep_time:
            rang.z_max = ep_time
        result = range_query(rang)
        record_count = len(result)
        record_sum += record_count
time_end = time.time()
print('range_query_time cost:', time_end - time_start, 's')
print('visit time:', visit_time)
print('record sum:', record_sum)


# 动态装入 ep2~ep10
flag = 0
for ep in range(2, 11):
    visit_time = 0
    data_buffer = Buffer()
    data_buffer.max_size = 128
    data_buffer.id_list = []
    data_buffer.block_dict = {}
    index_buffer = Buffer()
    index_buffer.max_size = 512
    index_buffer.id_list = []
    index_buffer.block_dict = {}
    print('ep' + str(ep))
    time_start = time.time()
    for i in range(300):
        with open(DATA + '/EP'+str(ep)+'/' + str(i) + '.txt') as file_object:
            for line in file_object:
                line = line.rstrip()
                line = line.split(",")
                r = Record()
                r.x = float(line[3])
                r.y = float(line[4])
                r.z = int(line[1])
                insert(r)
    # 将grid array 写入硬盘
    index_file = open(index_file_name, 'wb')
    for i in range(nx):
        for j in range(ny):
            for k in range(nz):
                bucket_id = st.pack("q", grid_array[i][j][k])
                index_file.write(bucket_id)
    index_file.close()
    # 将桶中数据写入硬盘
    data_file = open(data_file_name, 'wb')
    for i in range(num):
        write_block(B[i])
    data_file.close()
    time_end = time.time()
    print('cost of maintain time:', time_end - time_start, 's')
    print('flag = ' + str(flag))
    print('nx = ' + str(nx))
    print('ny = ' + str(ny))
    print('nz = ' + str(nz))
    print('x = ' + str(len(X)))
    print('y = ' + str(len(Y)))
    print('z = ' + str(len(Z)))
    print(X)
    print(Y)
    print(Z)


# 周期更新点查询
# 一个索引块可以放1024(1000)个索引项 1000 * 8
# 一个数据块可以放341个数据
data_buffer = Buffer()
data_buffer.max_size = 128
data_buffer.id_list = []
data_buffer.block_dict = {}
index_buffer = Buffer()
index_buffer.max_size = 512
index_buffer.id_list = []
index_buffer.block_dict = {}
time_start = time.time()
success = 0
fail = 0
visit_time = 0
index_file = open(index_file_name, "rb")
data_file = open(data_file_name, "rb")
with open(point_query_file2_name) as file_object:
    for line in file_object:
        line = line.rstrip()
        line = line.split(",")
        r = Record()
        r.x = float(line[0])
        r.y = float(line[1])
        r.z = float(line[2])
        result = point_query(r)
        if result == 1:
            success += 1
        elif result == 0:
            fail += 1
time_end = time.time()
print('point_query_time cost:', time_end - time_start, 's')
print('visit time:', visit_time)


# 范围查询
data_buffer = Buffer()
data_buffer.max_size = 128
data_buffer.id_list = []
data_buffer.block_dict = {}
index_buffer = Buffer()
index_buffer.max_size = 512
index_buffer.id_list = []
index_buffer.block_dict = {}
record_sum = 0
visit_time = 0
time_start = time.time()
# 将索引块加入缓存区
index_file = open(index_file_name, "rb")
data_file = open(data_file_name, "rb")
with open(range_query_file_name) as file_object:
    for line in file_object:
        line = line.rstrip()
        line = line.split(",")
        rang = Range()
        rang.x_min = float(line[0])
        rang.x_max = float(line[1])
        rang.y_min = float(line[2])
        rang.y_max = float(line[3])
        rang.z_min = float(line[4])
        rang.z_max = float(line[5])
        if rang.z_max > ep_time:
            rang.z_max = ep_time
        result = range_query(rang)
        record_count = len(result)
        record_sum += record_count
time_end = time.time()
print('range_query_time cost:', time_end - time_start, 's')
print('visit time:', visit_time)
print('record sum:', record_sum)
