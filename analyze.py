from pydot import Dot, Edge, Node
def red_str(s):
    return "\033[1;31m%s\033[0m"%s

def sp(s , separator = ['\t',' ','\n']):
    """Split a string with multiple characters"""
    ans=[]
    i=j=0
    while j<len(s) and s[j] in separator:
        j+=1
    i=j
    while i<len(s):
        while j<len(s) and s[j] not in separator:
            j+=1
        ans.append(s[i:j])
        while j<len(s) and s[j] in separator:
            j+=1
        i=j
    return ans

class Resource:
    def __init__(self, name):
        self.name = name    #public
        self.synthesis_paths = []   #public

    def add_synthesis_path(self, synthesis_path):
        assert isinstance(synthesis_path, SynthesisPath)
        self.synthesis_paths.append(synthesis_path)

    def has_single_path(self):
        return len(self.synthesis_paths) <= 1

    def get_synthesis_path(self):
        assert self.has_single_path()   # temporary
        if len(self.synthesis_paths) == 0:
            return None
        return self.synthesis_paths[0]

class SynthesisPath:
    def __init__(self, idx, s, synthesis_manual):
        assert isinstance(s, str)
        assert isinstance(synthesis_manual, SynthesisManual)
        sp_s = sp(s)
        rate = eval(sp_s[0])
        self.idx = idx
        self.time = eval(sp_s[-1]) / rate #second
        self.coef = [eval(i) / rate for i in sp_s[:-1:2]]
        self.product = synthesis_manual.get_resource_by_name(sp_s[1])
        self.product.add_synthesis_path(self)
        self.ingredients = [synthesis_manual.get_resource_by_name(name) for name in sp_s[3:-1:2]]
    
    def __repr__(self):
        return "<%d> %s <- "%(self.idx, self.product.name) + ' '.join([p.name for p in self.ingredients])

class SynthesisManual:
    def __init__(self, file_name):
        assert isinstance(file_name, str)
        self.resource_dict = {} #dict<str,Resource>
        self.file_name = file_name
        self.parse_file()
    
    def parse_file(self):
        with open(self.file_name, 'r') as f:
            for idx, line in enumerate(f):
                if line.strip().startswith(";") or line.strip() == '':    # skip comments and empty lines
                    continue
                SynthesisPath(idx, line, self)

    def register_resource(self, name):
        assert name not in self.resource_dict
        self.resource_dict[name] = Resource(name)

    def get_resource_by_name(self, name):
        if name not in self.resource_dict:
            self.register_resource(name)
        return self.resource_dict[name]

class SynthesisGraphNode:
    def __init__(self,name,synthesis_graph):
        self.name = name
        self.before = []
        self.next = []
        self.resource = synthesis_graph.synthesis_manual.get_resource_by_name(name)
        assert self.resource.has_single_path() # temporary
        self.syn_path = self.resource.get_synthesis_path()
        if self.syn_path:
            self.time_needed = self.syn_path.time   # seconds needed for synthesis
            for res, coef in zip(self.syn_path.ingredients, self.syn_path.coef):
                node = synthesis_graph.get_node_by_name(res.name)
                self.before.append((node, coef))
                node.next.append((self, coef))
        else:
            self.time_needed = 0
        
        self.speed = 0 # per minute
        self.speed_fixed = False    # the speed hasn't been fixed yet
        self.num_factory = 0

        self.dumped = False # only True on dumping process
        
    def add_next(self, node, coef):
        assert isinstance(node, SynthesisGraphNode)
        assert isinstance(coef, int) or isinstance(coef, float)
        self.next.append((node,coef))

    def set_speed(self, speed):
        self.speed = speed
        self.fix_speed()

    def fix_speed(self):
        self.num_factory = self.speed * self.time_needed / 60
        self.speed_fixed = True
        for node, _ in self.before:
            if node.all_next_fixed():
                node.calc_speed()

    def all_next_fixed(self):
        for node, _ in self.next:
            if not node.speed_fixed:
                return False
        return True
    
    def all_next_dumped(self):
        for node, _ in self.next:
            if not node.dumped:
                return False
        return True

    def calc_speed(self):
        assert self.all_next_fixed()
        self.speed = sum([node.speed * coef for node, coef in self.next])
        print(self.name, self.speed)
        self.fix_speed()
    
    def get_content(self):
        if self.num_factory < 1e-3:
            return "%s\n%.2f\n..."%(self.name, self.speed)
        return "%s\n%.2f\n%.1f"%(self.name, self.speed, self.num_factory)

    def dump_to(self,dot_obj):
        assert isinstance(dot_obj, Dot)
        color = 'black'
        style = 'default'
        if len(self.next) == 0:
            color = 'yellow'
            style = 'filled'
        if len(self.before) == 0:
            color = 'green'
        if self.num_factory < 1e-3:
            color = 'red'
        dot_obj.add_node(Node(self.get_content(), color = color, style = style))
        self.dumped = True
        for n, _ in self.next:
            dot_obj.add_edge(Edge(self.get_content(), n.get_content()))

        for n, _ in self.before:
            if n.all_next_dumped() and not n.dumped:
                n.dump_to(dot_obj)

class SynthesisGraph:
    def __init__(self,target_names,speeds,synthesis_manual):
        assert isinstance(target_names, list)
        assert isinstance(speeds, list)
        assert isinstance(synthesis_manual, SynthesisManual)
        self.synthesis_manual = synthesis_manual
        self.node_dict = {}
        self.target_nodes = []
        for target_name, speed in zip(target_names, speeds):
            target_node = self.get_node_by_name(target_name)   #build graph
            target_node.set_speed(speed)   #calc on graph
            self.target_nodes.append(target_node)

    def register_node(self, name):
        assert isinstance(name, str)
        assert name not in self.node_dict
        self.node_dict[name] = SynthesisGraphNode(name,self)
    
    def get_node_by_name(self, name):
        assert isinstance(name, str)
        if name not in self.node_dict:
            self.register_node(name)
        return self.node_dict[name]
    
    def dump(self):
        """export to a dot file"""
        for nm in self.node_dict.keys():
            self.get_node_by_name(nm).dumped = False
        g = Dot()
        for n in self.target_nodes:
            n.dump_to(g)
        from time import time
        file_name = '_'.join([n.name for n in self.target_nodes])
        file_name += '_%d.png'%(time()%100003)
        g.write_png(file_name)

def debug_mode():
    while True:
        try:
            print(eval(input(">>> ")))
        except Exception as e:
            print(e)

if __name__ == '__main__':
    syn_man = SynthesisManual('data.txt')
    #syn_graph = SynthesisGraph(['电磁矩阵','能量矩阵','结构矩阵','信息矩阵','引力矩阵'],[60,60,60,60,60],syn_man)
    syn_graph = SynthesisGraph(['引力矩阵'],[60],syn_man)
    syn_graph.dump()