#!/usr/bin/python


# Implementation for graph of which nodes are spans of sentence 
# author Chuan Wang

import copy
import sys,re
from util import StrLiteral,Polarity,Quantity,ConstTag
from util import ispunctuation
from constants import NULL_TAG,NULL_EDGE,PRE_MERGE_NETAG
from common.AMRGraph import *



class SpanNode(object):
    def __init__(self,start,end,words,tag=NULL_TAG):
        self.start = start
        self.end = end
        self.tag = tag
        self.words = words
        self.children = []
        self.parents = [] 
        self.SWAPPED = False
        self.num_swap = 0
        self.del_child = [] # record the replaced or deleted child
        self.rep_parent = [] # record the parent replaced

    @staticmethod
    def from_span(span):
        """initialize from span object"""
        return SpanNode(span.start,span.end,span.words,span.entity_tag)

    def addChild(self,child):
        #if isinstance(c,list):
        #    self.children.extend(c)
        #else:
        if child not in self.children:
            self.children.append(child)

    def contains(self,other_node):
        if other_node.start >= self.start and other_node.end <= self.end and \
           not (other_node.start == self.start and other_node.end == self.end):
            return True
        else:
            return False

    def addParent(self,parent):
        if parent not in self.parents:
            self.parents.append(parent)

    def removeChild(self,child):
        self.children.remove(child)
        
    def removeParent(self,parent):
        self.parents.remove(parent)

    def __str__(self):
        return 'Span node:(%s,%s) Children: %s SWAPPED:%s'%(self.start,self.end,self.children,self.SWAPPED)
    def __repr__(self):
        return 'Span node:(%s,%s) Children: %s SWAPPED:%s'%(self.start,self.end,self.children,self.SWAPPED)

class SpanGraph(object):
    """
    Graph of span nodes
    """
    LABELED = False
    graphID = 0

    def __init__(self):
        self.root = 0 # this is actually the unique top
        self.multi_roots = []
        self.nodes = {} # refer to spans by start index
        self.edges = {} # refer to edges by tuple (parent,child)
        self.sent = None        
        self.static_tuples = set([]) # cache the tuples so that we don't have to traverse the graph everytime

    @staticmethod
    def init_ref_graph(amr,alignment,sent=None):
        """Instantiate graph from AMR graph and alignment"""
        SpanGraph.graphID += 1
        spgraph = SpanGraph()
        span_alignment = alignment
        spgraph.sent = sent
        #DepGraph.LABELED = LABELED
        vars = [node.node_label for node in amr.dfs()[0]]
        unaligned_vars = set([])
        and_nodes = set([])

        for h in vars:
            hconcept = amr.node_to_concepts[h] if h in amr.node_to_concepts else h
            if not h in span_alignment: # ignore unaligned concept
                unaligned_vars.add(h) 
                continue
            hspans = span_alignment[h]
            if len(hspans) < 2:
                hspan = hspans[0]
            else:
                hspan = hspans.pop(0)
            if not hspan.start in spgraph.nodes:
                h_node = SpanNode.from_span(hspan)
                spgraph.add_node(h_node)
                if hconcept == 'and': and_nodes.add(h_node.start)
            for edge,ds in amr[h].items():
                d = ds[0]
                dconcept = amr.node_to_concepts[d] if d in amr.node_to_concepts else d
                if not d in span_alignment:
                    unaligned_vars.add(d)
                    continue
                dspans = span_alignment[d]
                if len(dspans) < 2:
                    dspan = dspans[0]
                else:
                    dspan = dspans.pop(0)
                if hspan.contains(dspan): # ignore internal structure
                    continue
                if not dspan.start in spgraph.nodes:
                    d_node = SpanNode.from_span(dspan)
                    spgraph.add_node(d_node)
                    if dconcept == 'and': and_nodes.add(d_node.start)
                spgraph.add_edge(hspan.start,dspan.start,edge)                            


        #if SpanGraph.graphID == 2069:
        #    import pdb
        #    pdb.set_trace()
            
        root = SpanNode(0,1,['root'],'O')
        spgraph.add_node(root)
        #hchild_id = 0
        if amr.roots[0] in span_alignment:
            hchild_id = span_alignment[amr.roots[0]][0].start
            spgraph.add_edge(0,hchild_id)
        else:
            print >> sys.stderr, "GraphID:%s WARNING:root %s not aligned!"%(SpanGraph.graphID,amr.node_to_concepts[amr.roots[0]])
            
            '''
            # make up a fake root that connect all the multi-roots
            root_str = amr.node_to_concepts[amr.roots[0]]
            fake_root = SpanNode('x','x+1',[root_str],root_str)
            hchild_id = 'x'
            spgraph.add_node(fake_root)
            spgraph.add_edge(0,hchild_id)

            #for edge,child in amr[amr.roots[0]].items():
            #    if child[0] in span_alignment:
            #        node_id = span_alignment[child[0]][0].start
            #        spgraph.add_edge(hchild_id,node_id,edge)
            '''
        # for other disconnected multi roots, we all link them to the root, here we ignore graphs with circle
        for node_id in spgraph.nodes:
            if spgraph.nodes[node_id].parents == [] and node_id != 0 and not spgraph.isContained(node_id): # multi-roots
                if spgraph.nodes[node_id].children:
                    spgraph.add_edge(0,node_id,'x')
                spgraph.multi_roots.append(node_id)

        # fix some of the 'and' alignment problem
        and_nodes = list(and_nodes)
        for i in range(len(and_nodes)):
            first_and = and_nodes[i]
            children = sorted(spgraph.nodes[first_and].children)
            if children:
                min = children[0]
                max = children[-1]
                if first_and < min or first_and > max: # need fix
                    for j in range(i+1,len(and_nodes)):
                        second_and = and_nodes[j]
                        schildren = sorted(spgraph.nodes[second_and].children)
                        if schildren:
                            smin = schildren[0]
                            smax = schildren[-1]
                            if second_and < max and second_and > min and first_and < smax and first_and > smin:
                                tmp1_parents = spgraph.nodes[first_and].parents[:]
                                tmp1_children = spgraph.nodes[first_and].children[:]

                                tmp_parents = spgraph.nodes[second_and].parents[:]
                                tmp_children = spgraph.nodes[second_and].children[:]
                                for p in tmp1_parents:
                                    edge_label = spgraph.get_edge_label(p,first_and)
                                    if p != second_and:
                                        spgraph.remove_edge(p,first_and)
                                        spgraph.add_edge(p,second_and,edge_label)
                                    else:
                                        spgraph.remove_edge(p,first_and)
                                        spgraph.add_edge(first_and,p,edge_label)
                                        
                                for c in tmp1_children:
                                    edge_label = spgraph.get_edge_label(first_and,c)
                                    if c != second_and:
                                        spgraph.remove_edge(first_and,c)
                                        spgraph.add_edge(second_and,c,edge_label)
                                    else:
                                        spgraph.remove_edge(first_and,c)
                                        spgraph.add_edge(c,first_and,edge_label)

                                for sp in tmp_parents:
                                    if sp != first_and:
                                        edge_label = spgraph.get_edge_label(sp,second_and)
                                        if sp not in tmp1_parents: #share parent
                                            spgraph.remove_edge(sp,second_and)
                                        spgraph.add_edge(sp,first_and,edge_label)
                                for sc in tmp_children:
                                    if sc != first_and:
                                        edge_label = spgraph.get_edge_label(second_and,sc)
                                        spgraph.remove_edge(second_and,sc)
                                        spgraph.add_edge(first_and,sc,edge_label)
                                

                        
        return spgraph


    @staticmethod
    def init_dep_graph(instance,sent=None):
        """instantiate graph from data instance"""
        dpg = SpanGraph()
        dpg.sent = sent
        for tok in instance.tokens:
            if tok['id'] == 0: # root
                root_form = tok['form']
                dpg.add_node(SpanNode(0,1,[root_form]))
                dpg.multi_roots.append(0)
            elif 'head' in tok:
                gov_id = tok['head']
                gov_form = instance.tokens[gov_id]['form']
                gov_netag = instance.tokens[gov_id]['ne']
                if gov_id not in dpg.nodes:
                    dpg.add_node(SpanNode(gov_id,gov_id+1,[gov_form]))
                if 'head' not in instance.tokens[gov_id] and gov_id not in dpg.multi_roots:
                    dpg.multi_roots.append(gov_id)
                    
                dep_id = tok['id']
                dep_form = tok['form']
                dep_netag = tok['ne']
                dep_label = tok['rel']
                if dep_id not in dpg.nodes:
                    dpg.add_node(SpanNode(dep_id,dep_id+1,[dep_form]))
                dpg.add_edge(gov_id,dep_id)
                    
            else:  # punctuation
                punc_id = tok['id']
                punc_form = tok['form']
                if punc_id not in dpg.multi_roots: dpg.multi_roots.append(punc_id)
                if punc_id not in dpg.nodes:
                    dpg.add_node(SpanNode(punc_id,punc_id+1,[punc_form]))
            
        if not dpg.nodes: # dependency tree is empty
            root = SpanNode(0,1,['root'],'O')
            dpg.multi_roots.append(0)
            dpg.add_node(root)
        #elif 0 not in dpg.nodes:
        #    dpg.make_root()
        return dpg


    def pre_merge_netag(self,instance):
        ne_spans = instance.get_ne_span(PRE_MERGE_NETAG)
        for ne_id,span in ne_spans.items():
            for sp_id in span:
                if sp_id != ne_id and ne_id in self.nodes and sp_id in self.nodes:
                    self.merge_node(ne_id,sp_id)
                    if sp_id in self.multi_roots: self.multi_roots.remove(sp_id)

    '''
    def init_dep_graph(stp_deps):
        """instantiate graph from dependency tuples"""
        dpg = SpanGraph()
        for line in stp_deps:
            line = line.strip()
            label = line.split('(')[0]
            
            gov_str,gov_idx = line.split('(')[1].split(',',1)[0].rsplit('-',1)
            gov_str = gov_str.strip()
            gov_idx = int(gov_idx)
            if not gov_idx in dpg.nodes:
                gov_node = SpanNode(gov_idx,gov_idx+1,[gov_str])
                dpg.add_node(gov_node)
            
            dep_str,dep_idx = line.split('(')[1].split(',',1)[1][:-1].rsplit('-',1)
            dep_str = dep_str.strip()
            dep_idx = int(dep_idx)
            if not dep_idx in dpg.nodes:
                dep_node = SpanNode(dep_idx,dep_idx+1,[dep_str])
                dpg.add_node(dep_node)
            dpg.add_edge(gov_idx,dep_idx)

        if not dpg.nodes:
            root = SpanNode(0,1,['root'],'O')
            dpg.add_node(root)
        elif 0 not in dpg.nodes:
            dpg.make_root()
        return dpg
    '''

    def make_root(self):
        first = sorted(self.nodes.keys())[0]
        root = SpanNode(0,1,['root'],'O')
        self.multi_roots.append(0)
        self.add_node(root)
        self.add_edge(0,first)
        #for c in self.nodes[first].children:
        #    self.remove_edge(first,c)
        #    self.add_edge(0,c)            
        
    def is_empty(self):
        return len(self.nodes.keys()) == 0

    def is_root(self):
        return self.nodes.keys() == [0]

    def numNodes(self):
        return len(self.nodes.keys())

    def nodes_list(self):
        return self.nodes.keys()

    def isContained(self,node_id):
        """check whether node is contained by some node in graph"""
        
        for k in self.nodes:
            if node_id in self.nodes:
                node = self.nodes[node_id]
                if node_id > k and node.end <= self.nodes[k].end:
                    return k
            else:
                if node_id > k and node_id < self.nodes[k].end:
                    return k
        return False
                

    def add_node(self,node):
        self.nodes[node.start] = node

    def add_edge(self,gov_index,dep_index,edge=NULL_EDGE):
        self.nodes[gov_index].addChild(dep_index)
        self.nodes[dep_index].addParent(gov_index)
        self.edges[tuple((gov_index,dep_index))] = edge

    def set_node_tag(self,idx,tag):
        self.nodes[idx].tag = tag
    
    def get_node_tag(self,idx):
        return self.nodes[idx].tag 
    
    def get_edge_label(self,gov_index,dep_index):
        return self.edges[tuple((gov_index,dep_index))] 

    def set_edge_label(self,gov_index,dep_index,edge_label):
        self.edges[tuple((gov_index,dep_index))] = edge_label

    def get_direction(self,i,j):
        """left or right or no arc"""
        if j in self.nodes[i].children:
            return 0
        elif i in self.nodes[j].children:
            return 1
        else:
            return -1
    
    def record_rep_head(self,cidx,idx):
        self.nodes[cidx].rep_parent.append(idx)

    def remove_node(self,idx,RECORD=False):
        for p in self.nodes[idx].parents[:]:
            self.remove_edge(p,idx)
            if RECORD: self.nodes[p].del_child.append(idx)
        for c in self.nodes[idx].children[:]:
            self.remove_edge(idx,c)
        del self.nodes[idx]
        if idx in self.multi_roots: self.multi_roots.remove(idx)
        
    # ignore the multiedge between same nodes 
    def remove_edge(self,gov_index,dep_index):
        self.nodes[gov_index].removeChild(dep_index)
        self.nodes[dep_index].removeParent(gov_index)
        if (gov_index,dep_index) in self.edges:
            del self.edges[(gov_index,dep_index)]

    def swap_head(self,gov_index,dep_index):
        """
        just flip the position of gov and dep
        """
        '''
        self.nodes[dep_index].addChild(gov_index)
        self.nodes[gov_index].removeChild(dep_index)
        children = self.nodes[gov_index].children
        self.nodes[dep_index].addChild(children)
        self.nodes[gov_index].children = []
        for c in children[:]:
            self.nodes[c].removeParent(gov_index)
            self.nodes[c].addParent(dep_index)

        parents = self.nodes[gov_index].parents
        self.nodes[dep_index].parents = parents
        self.nodes[gov_index].parents = [dep_index]
        for p in parents[:]:
            self.nodes[p].removeChild(gov_index)
            self.nodes[p].addChild(dep_index)
        '''
        tmp_parents = self.nodes[dep_index].parents[:]
        tmp_children = self.nodes[dep_index].children[:]
        for p in self.nodes[gov_index].parents[:]:
            if p != dep_index:
                edge_label = self.get_edge_label(p,gov_index)
                self.remove_edge(p,gov_index)
                self.add_edge(p,dep_index,edge_label)
        for c in self.nodes[gov_index].children[:]:
            if c != dep_index:
                edge_label = self.get_edge_label(gov_index,c)
                self.remove_edge(gov_index,c)
                self.add_edge(dep_index,c,edge_label)
            else:
                self.remove_edge(gov_index,c)
                self.add_edge(c,gov_index)
                
        for sp in tmp_parents:
            if sp != gov_index:
                edge_label = self.get_edge_label(sp,dep_index)
                self.remove_edge(sp,dep_index)
                self.add_edge(sp,gov_index,edge_label)
            #else:
            #    self.remove_edge(sp,dep_index)
                
        for sc in tmp_children:
            if sc != gov_index:
                edge_label = self.get_edge_label(dep_index,sc)
                self.remove_edge(dep_index,sc)
                self.add_edge(gov_index,sc,edge_label)
        
        self.nodes[gov_index].SWAPPED = True
            
    def reattach_node(self,idx,cidx,parent_to_attach,edge_label):
        self.remove_edge(idx,cidx)
        if parent_to_attach is not None:
            self.add_edge(parent_to_attach,cidx,edge_label)
        

    def swap_head2(self,gov_index,dep_index,sigma,edge_label=None):
        """
        keep dep and gov's dependents unchanged, only switch the dependency edge 
        direction, also all gov's parents become dep's parents
        """
        #
        for p in self.nodes[gov_index].parents[:]:
            if p != dep_index and p in sigma:
                self.remove_edge(p,gov_index)
                self.add_edge(p,dep_index)
                
        if dep_index in self.nodes[gov_index].parents:
            self.remove_edge(gov_index,dep_index)
        else:            
            #self.nodes[gov_index].removeChild(dep_index)
            #self.nodes[gov_index].addParent(dep_index)

            #self.nodes[dep_index].removeParent(gov_index)
            #self.nodes[dep_index].addChild(gov_index)
            self.remove_edge(gov_index,dep_index)
            self.add_edge(dep_index,gov_index,edge_label)
            self.nodes[gov_index].SWAPPED = True
            self.nodes[dep_index].num_swap += 1
        
    def replace_head(self,idx1,idx2):
        for c in self.nodes[idx1].children[:]:
            if c != idx2 and c not in self.nodes[idx2].children:
                if c not in self.nodes[idx2].parents: # no multi-edge no circle
                    self.add_edge(idx2,c)
                                        
        for p in self.nodes[idx1].parents[:]:
            if p != idx2: self.add_edge(p,idx2)
            
        self.remove_node(idx1,RECORD=True)

    def merge_node(self,idx1,idx2):
        '''merge nodes connecting current arc (idx1,idx2) '''
        '''
        lr = self.get_direction(idx1,idx2)
        if lr == 0:
            self.remove_edge(idx1,idx2)
        elif lr == 1:
            self.remove_edge(idx2,idx1)
        else:
            print >> sys.stderr, "WARNING: no edge between merged nodes!"
        '''
        tmp1 = idx1
        tmp2 = idx2
        idx1 = tmp1 if tmp1 < tmp2 else tmp2
        idx2 = tmp2 if tmp1 < tmp2 else tmp1
        self.nodes[idx1].end = self.nodes[idx2].end if self.nodes[idx1].end < self.nodes[idx2].end else self.nodes[idx1].end
        self.nodes[idx1].words.extend(self.nodes[idx2].words)
        #self.nodes[idx1].parents.extend([p1 for p1 in self.nodes[idx2].parents if p1 not in self.nodes[idx1].parents])
        for p in self.nodes[idx2].parents[:]:
            #self.nodes[p].children.remove(idx2)
            #self.nodes[p].addChild(idx1)
            if p != idx1 and p not in self.nodes[idx1].parents:
                edge_label = self.get_edge_label(p,idx2)
                self.add_edge(p,idx1,edge_label)
        #self.nodes[idx1].children.extend([c1 for c1 in self.nodes[idx2].children if c1 not in self.nodes[idx1].children and c1 != idx1])
        for c in self.nodes[idx2].children[:]:
            #self.nodes[c].parents.remove(idx2)
            #self.nodes[c].addParent(idx1)
            if c != idx1 and c not in self.nodes[idx1].children:
                edge_label = self.get_edge_label(idx2,c)
                self.add_edge(idx1,c,edge_label)
        self.remove_node(idx2)
        self.nodes[idx1].SWAPPED = False        
    
    def get_multi_roots(self):
        multi_roots = []
        for n in self.nodes.keys():
            if self.nodes[n].parents == []  and self.nodes[n].children != []:  # root TODO: Detect root with circle    
                multi_roots.append(n)
        return multi_roots


    def bfs(self, root=0, OUTPUT_NODE_SET=False):
        """if given root and graph is connected, we can do breadth first search"""
        from collections import deque
        visited_nodes = set()
        dep_tuples = []

        queue = deque([root])
        while queue:
            next = queue.popleft()
            if next in visited_nodes:
                continue
            visited_nodes.add(next)
            for child in sorted(self.nodes[next].children):
                if not (next,child) in dep_tuples:
                    if not child in visited_nodes:
                        queue.append(child)
                    dep_tuples.append((next,child))
        return visited_nodes,dep_tuples

    def tuples(self):
        """traverse the graph in index increasing order"""
        graph_tuples = []
        node_set = set()
        for n in sorted(self.nodes.keys()):
            if (self.nodes[n].parents == [] or n not in node_set) and self.nodes[n].children != []:  # root   
                visited_nodes,sub_tuples = self.bfs(n,True)
                graph_tuples.extend([st for st in sub_tuples if st not in graph_tuples])
                node_set.update(visited_nodes)
        return graph_tuples

    def postorder(self,root=0,seq=None):
        """only for dependency trees"""
        if seq is None:
            seq = []
        if self.nodes[root].children == []:
            seq.append(root)
            #pass
        else:
            for child in self.nodes[root].children:
                self.postorder(child,seq)
            seq.append(root)
        return seq
    
    def leaves(self):
        """return all the leaves ordered by their indexes in the sentence"""
        leaves = []
        for nidx in self.nodes:
            if self.nodes[nidx].children == []:
                leaves.append(nidx)
        return sorted(leaves)
    
    def locInTree(self,idx):        
        depth = 0 
        candidates = self.leaves()
        while idx not in candidates:
            candidates = sorted(list(set([self.nodes[l].parents[0] for l in candidates if self.nodes[l].parents])))
            depth +=1 
        assert idx in candidates
        return (candidates.index(idx),depth)
        
    def path(self,idx):
        """path from root, only for tree structure"""
        path = []
        cur = self.nodes[idx]
        path.insert(0,idx)
        while cur.parents:
            cur = self.nodes[cur.parents[0]]
            path.insert(0,cur.start)
            
        return path
        
    def get_path(self,idx1,idx2):
        """path between two nodes, only for tree structure"""
        path1 = self.path(idx1)
        path2 = self.path(idx2)
        direction = '01'
        lenth = len(path1) if len(path1) < len(path2) else len(path2)
        for i in range(lenth):
            if path1[i] != path2[i]:
                break
        if path1[i] == path2[i]:            
            if len(path1) > len(path2):
                path = list(reversed(path1[i:]))
                direction = '0' 
            else:
                path = path2[i:]
                direction = '1'
        else:
            path = list(reversed(path1[i-1:]))+path2[i:]

        return path,direction
        
    def relativePos(self,currentIdx,otherIdx):
        cindex,cdepth = self.locInTree(currentIdx)
        oindex,odepth = self.locInTree(otherIdx)
        return (cindex-oindex,cdepth-odepth)  
    
    def relativePos2(self,currentIdx,otherIdx):
        cpath = self.path(currentIdx)
        opath = self.path(otherIdx)

        #if otherIdx != 0 and otherIdx != currentIdx and \
        #   otherIdx not in self.nodes[currentIdx].parents and \
        #   otherIdx not in self.nodes[currentIdx].children:
        type = None
        if True:
            if len(cpath) > 1 and len(opath) > 1:
                if cpath[-2] == opath[-2]: # same parent
                    type = 'SP'

            if len(cpath) > 2 and len(opath) > 2:
                if cpath[-3] == opath[-3] and cpath[-2] != opath[-2]: # same grand parent not same parent
                    if not type:
                        type = 'SGP'
                    else:
                        raise Exception("Not mutual exclusive child type")
                if cpath[-3] == opath[-2] and opath[-1] != cpath[-2]: # current node's parent's brother
                    #return 'PB'
                    if not type:
                        type = 'PB'
                    else:
                        raise Exception("Not mutual exclusive child type")
                if opath[-3] == cpath[-2] and cpath[-1] != opath[-2]: # other node's parent's brother
                    #return 'rPB'
                    if not type:
                        type = 'rPB'
                    else:
                        raise Exception("Not mutual exclusive child type")
                if opath[-1] in cpath: # otherIdx on currentIdx's path
                    #return 'P'+str(len(cpath)-1-cpath.index(opath[-1]))
                    #return 'P'
                    if not type:
                        type = 'P'
                    else:
                        raise Exception("Not mutual exclusive child type")
                if cpath[-1] in opath: # currentIdx on otherIdx's path
                    #return 'rP'+str(len(opath)-1-opath.index(cpath[-1]))
                    #return 'rP'
                    if not type:
                        type = 'rP'
                    else:
                        raise Exception("Not mutual exclusive child type")

        return type if type else 'O'
        
    def get_possible_children_unconstrained(self,currentIdx):
        """return all the other nodes in the tree not violated the rules"""
        candidate_children = []
        for otherIdx in self.nodes:
            if otherIdx != 0 and otherIdx != currentIdx and \
                otherIdx not in self.nodes[currentIdx].children:
                candidate_children.append(otherIdx)
    
        return candidate_children

    def get_possible_parent_unconstrained(self,currentIdx,currentChildIdx):
        candidate_parents = set([])
        for otherIdx in self.nodes:
            if otherIdx != 0 and otherIdx != currentChildIdx and \
               otherIdx not in self.nodes[currentChildIdx].parents:
                candidate_parents.add(otherIdx)
        return candidate_parents


    def get_possible_reentrance_constrained(self,currentIdx,currentChildIdx):
        '''adding siblings, mainly for control verb'''
        #if self.nodes[currentIdx].parents:
        cur_p = self.nodes[currentIdx]
        result_set = set([])
        if len(cur_p.children) > 1:
            result_set = set([sb for sb in cur_p.children if sb != currentChildIdx and sb not in self.nodes[currentChildIdx].parents and sb not in self.nodes[currentChildIdx].children])
        '''
        cur_p = self.nodes[currentIdx]
        j=0
        while cur_p.parents and j < i:
            cur_gp = cur_p.parents[0]
            result_set.add(cur_gp)
            cur_p = self.nodes[cur_gp]
            j+=1
        '''
        return result_set
        
    def get_possible_parent_constrained(self,currentIdx,currentChildIdx,i=2):
        '''promotion: only add ancestors 2 levels up the current node'''
        children = sorted(self.nodes[currentIdx].children)
        c = children.index(currentChildIdx)
        candidate_parents= set([])
        visited = set([])
        
        if c > 0:
            left_sp = self.nodes[children[c-1]]
            candidate_parents.add(children[c-1])
            visited.add(children[c-1])
            while left_sp.children:
                ls_r_child = sorted(left_sp.children)[-1]
                #if ls_r_child in candidate_parents: break
                if ls_r_child in visited: break
                visited.add(ls_r_child)
                if ls_r_child != currentChildIdx and ls_r_child not in self.nodes[currentChildIdx].children and ls_r_child not in self.nodes[currentChildIdx].parents:
                    candidate_parents.add(ls_r_child)
                left_sp = self.nodes[ls_r_child]

        if c < len(children) - 1:
            right_sp = self.nodes[children[c+1]]
            candidate_parents.add(children[c+1])
            visited.add(children[c+1])
            while right_sp.children:
                rs_l_child = sorted(right_sp.children)[0]
                #if rs_l_child in candidate_parents: break
                if rs_l_child in visited: break
                visited.add(rs_l_child)
                if rs_l_child != currentChildIdx and rs_l_child not in self.nodes[currentChildIdx].children and rs_l_child not in self.nodes[currentChildIdx].parents:
                    candidate_parents.add(rs_l_child)
                right_sp = self.nodes[rs_l_child]
        
        cur_p = self.nodes[currentIdx]
        j=0
        while cur_p.parents and j < i:
            cur_gp = cur_p.parents[0]
            candidate_parents.add(cur_gp)
            cur_p = self.nodes[cur_gp]
            j+=1
        sep_nodes = self.multi_roots[:]
        sep_nodes.remove(0)
        candidate_parents.update(sep_nodes)
        return candidate_parents
        
                
    def get_possible_children(self,currentIdx):
        """only for tree structure, get all the candidate children for current node idx"""
        cpath = self.path(currentIdx)
        possible_children = []
        num_SP = 0
        num_SGP = 0
        num_PB = 0
        num_rPB = 0
        num_P = 0
        num_rP = 0
        num_other = 0
        num_total = 0

        for otherIdx in self.nodes:
            if otherIdx != 0 and otherIdx != currentIdx and \
               otherIdx not in self.nodes[currentIdx].parents and \
               otherIdx not in self.nodes[currentIdx].children:
                num_total += 1
                opath = self.path(otherIdx)
                if len(cpath) > 1 and len(opath) > 1 and cpath[-2] == opath[-2]:                    
                    possible_children.append('SP'+str(num_SP))
                    num_SP +=1 

                if len(cpath) > 2 and len(opath) > 2 and cpath[-3] == opath[-3] and cpath[-2] != opath[-2]:                
                    possible_children.append('SGP'+str(num_SGP))
                    num_SGP +=1 

                if len(cpath) > 2 and len(opath) > 2 and cpath[-3] == opath[-2] and opath[-1] != cpath[-2]:
                    possible_children.append('PB'+str(num_PB))
                    num_PB +=1 

                if len(cpath) > 2 and len(opath) > 2 and cpath[-2] == opath[-3] and cpath[-1] != opath[-2]:
                    possible_children.append('rPB'+str(num_rPB))
                    num_rPB += 1

                if len(cpath) > 0 and len(opath) > 0 and opath[-1] in cpath:
                    possible_children.append('P'+str(num_P))
                    num_P += 1

                if len(cpath) > 0 and len(opath) > 0 and cpath[-1] in opath:
                    possible_children.append('rP'+str(num_rP))
                    num_rP += 1

                    
                assert num_total == len(possible_children)

        return possible_children
        
                        
    def is_produce_circle(self,currentIdx,node_to_add):
        currentNode = self.nodes[currentIdx]
        stack = [currentIdx]
        while stack:
            next = stack.pop()

            parents = self.nodes[next].parents
            if parents:
                if node_to_add in parents:
                    return True
                else:
                    stack.extend(self.nodes[next].parents)
        return False

    def flipConst(self):
        '''
        since in amr const variable will not have children
        we simply flip the relation when we run into const variable as parent
        '''
        for parent,child in self.tuples():
            if (isinstance(self.nodes[parent].tag,ConstTag) or r'/' in self.nodes[parent].tag) and not isinstance(self.nodes[child].tag,ConstTag): 
                for p in self.nodes[parent].parents[:]:
                    if p != child:
                        self.remove_edge(p,parent)
                        self.add_edge(p,child)
                
                if child in self.nodes[parent].parents:
                    self.remove_edge(parent,child)
                else:            
                    #self.nodes[gov_index].removeChild(dep_index)
                    #self.nodes[gov_index].addParent(dep_index)
                    
                    #self.nodes[dep_index].removeParent(gov_index)
                    #self.nodes[dep_index].addChild(gov_index)
                    self.remove_edge(parent,child)
                    self.add_edge(child,parent)

            elif isinstance(self.nodes[parent].tag,ConstTag) and isinstance(self.nodes[child].tag,ConstTag):
                for p in self.nodes[parent].parents[:]:
                    if p != child:                
                        self.add_edge(p,child)
                self.remove_edge(parent,child)


    def print_tuples(self,bfs=False):
        """print the dependency graph as tuples"""
        if not self.sent:
            if bfs:
                return '\n'.join("(%s(%s-%s),(%s-%s))"%(self.get_edge_label(g,d),','.join(w for w in self.nodes[g].words), g,','.join(t for t in self.nodes[d].words), d) for g,d in self.bfs())
            else:
                return '\n'.join("(%s(%s-%s),(%s-%s))"%(self.get_edge_label(g,d),','.join(w for w in self.nodes[g].words), g,','.join(t for t in self.nodes[d].words), d) for g,d in self.tuples())
        else:
            output = ''
            if bfs:
                seq = self.bfs()
            else:
                seq = self.tuples()
                
            for g,d in seq:
                g_span = ','.join(tok['form'] for tok in self.sent[g:self.nodes[g].end]) if g!= 'x' else ','.join(self.nodes[g].words)
                d_span = ','.join(tok['form'] for tok in self.sent[d:self.nodes[d].end]) if d!= 'x' else ','.join(self.nodes[d].words)
                output += "(%s(%s-%s:%s),(%s-%s:%s))\n"%(self.get_edge_label(g,d), g_span, g, self.nodes[g].tag, d_span, d, self.nodes[d].tag)

            return output
                #return '\n'.join("(%s(%s-%s:%s),(%s-%s:%s))"%(self.get_edge_label(g,d),','.join(tok['form'] for tok in self.sent[self.nodes[g].start:self.nodes[g].end]), g, self.nodes[g].tag,','.join(tok['form'] for tok in self.sent[self.nodes[d].start:self.nodes[d].end]), d, self.nodes[d].tag) for g,d in self.bfs())

                #return '\n'.join("(%s(%s-%s:%s),(%s-%s:%s))"%(self.get_edge_label(g,d),','.join(tok['form'] for tok in self.sent[self.nodes[g].start:self.nodes[g].end]), g, self.nodes[g].tag,','.join(tok['form'] for tok in self.sent[self.nodes[d].start:self.nodes[d].end]), d, self.nodes[d].tag) for g,d in self.tuples())

    def getPGStyleGraph(self,focus=None):
        
        result = ''
        if focus:
            for g,d in self.tuples():
                if g == focus[0] or g == focus[1]:
                    gwords = '"%s-%d"[blue]'%(','.join(w for w in self.nodes[g].words),g)
                else:
                    gwords = '"%s-%d"'%(','.join(w for w in self.nodes[g].words),g)
                if d == focus[0] or d == focus[1]:
                    dwords = '"%s-%d"[blue]'%(','.join(w for w in self.nodes[d].words),d)
                else:
                    dwords = '"%s-%d"'%(','.join(w for w in self.nodes[d].words),d)
                if (g,d) == focus:
                    result += '%s ->[red] %s;\n'%(gwords,dwords)
                else:                    
                    result += '%s -> %s;\n'%(gwords,dwords)
            return result
        else:
            for g,d in self.tuples():
                gwords = ','.join(w for w in self.nodes[g].words)
                dwords = ','.join(w for w in self.nodes[d].words)
                result += '"%s-%d" -> "%s-%d";\n'%(gwords,g,dwords,d) 
            return result
            

