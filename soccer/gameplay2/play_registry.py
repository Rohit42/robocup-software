from PyQt4 import QtCore, QtGui


# The play registry keeps a tree of all plays in the 'plays' folder (and its subfolders)
# Our old system required programmatically registering plays into categories, but
# the new system just uses the filesystem hierarchy for this.
#
# The registry has methods for loading and unloading plays (for when files change on disk)
#
# It also tracks which plays are enabled
class PlayRegistry(QtCore.QAbstractItemModel):

    def __init__(self):
        super().__init__()
        self._root = PlayRegistry.Category(None, "")


    @property
    def root(self):
        return self._root
    

    # the module path is a list
    # for a demo play called RunAround, module_path = ['demo', 'run_around']
    # (note that we left out 'plays' - every play is assumed to be in a descendent module of it)
    def insert(self, module_path, play_class):
        category = self.root

        # iterate up to the last one (the last one is just an underscored,
        # lowercased version of the play's name and we don't display it in the tree)
        for module in module_path[:-1]:
            if module not in category.children:
                subcategory = PlayRegistry.Category(category, module)
                category.appendChild(subcategory)
            category = category[module]

        playNode = PlayRegistry.Node(module_path[-1], play_class)
        category.appendChild(playNode)


    def delete(self, module_path, play_class):
        catStack = [self.root]
        try:
            for module in module_path[:-1]:
                catStack.append(catStack[-1][module])
            
            # remove the play
            del catStack[-1][play_class.__name__]

            # remove any categories where this play was the only entry
            catStack.reverse()
            for idx, category in enumerate(catStack[:-1]):
                if len(category.children) == 0:
                    del catStack[idx+1][module_path[-2 - idx]]
        except KeyError:
            raise KeyError("Unable to find the specified play")


    # returns a list of all plays in the tree that are currently enabled
    def get_enabled_plays(self):
        return [node.play_class for node in self if node.enabled]


    # iterates over all of the Nodes registered in the tree
    def __iter__(self):
        def _recursive_iter(category):
            for child in category.children():
                if isinstance(child, PlayRegistry.Node):
                    yield child
                else:
                    yield from _recursive_iter(child)
        return _recursive_iter(self.root)


    def __contains__(self, play_class):
        for node in self:
            if node.play_class == play_class:
                return True
        return False


    def __str__(self):
        def _cat_str(category, indent):
            desc = ""
            for child in category.children:
                if isinstance(child, PlayRegistry.Node):
                    desc += "    " * indent
                    desc += str(child)
                else:
                    desc += "    " * indent + child.name + ':' + '\n'
                    desc += _cat_str(child, indent + 1)
                desc += '\n'
            return desc[:-1]    # delete trailing newline

        return "PlayRegistry:\n-------------\n" + _cat_str(self.root, 0)




    class Category():
        def __init__(self, parent, name):
            super().__init__()

            self._name = name
            self._parent = parent
            self._children = list()


        @property
        def name(self):
            return self._name


        def __del__(self, name):
            for idx, child in enumerate(self.children):
                if child.name == name:
                    del self.children[idx]
                    return
            raise KeyError("Attempt to delete a child node that doesn't exist")


        def appendChild(self, child):
            self.children.append(child)
            child.parent = self


        def __getitem__(self, name):
            for child in self.children:
                if child.name == name:
                    return child
            return None


        def has_child_with_name(self, name):
            return self[name] != None


        @property
        def parent(self):
            return self._parent
        @parent.setter
        def parent(self, value):
            self._parent = value
        


        # @children is a list
        @property
        def children(self):
            return self._children

        @property
        def row(self):
            if self.parent != None:
                return self.parent.children.index(self)
            else:
                return 0





    class Node():

        def __init__(self, module_name, play_class):
            self._module_name = module_name
            self._play_class = play_class
            self._enabled = True


        @property
        def parent(self):
            return self._parent
        @parent.setter
        def parent(self, value):
            self._parent = value
        

        @property
        def name(self):
            return self.play_class.__name__
        

        @property
        def module_name(self):
            return self._module_name

        @property
        def play_class(self):
            return self._play_class
        
        @property
        def enabled(self):
            return self._enabled
        @enabled.setter
        def enabled(self, value):
            self._enabled = value


        def __str__(self):
            return self.play_class.__name__ + " " + ("[ENABLED]" if self.enabled else "[DISABLED]")




    # Note: a lot of the QAbstractModel-specific implementation is borrowed from here:
    # http://www.hardcoded.net/articles/using_qtreeview_with_qabstractitemmodel.htm

    def columnCount(self, parent):
        return 1


    def flags(self, index):
        return QtCore.Qt.ItemIsEnabled | QtCore.Qt.ItemIsUserCheckable | QtCore.Qt.ItemIsEditable


    def data(self, index, role):
        if not index.isValid():
            return None
        node = index.internalPointer()
        if role == QtCore.Qt.DisplayRole and index.column() == 0:
            return node.name
        elif role == QtCore.Qt.CheckStateRole and isinstance(node, PlayRegistry.Node):
            return node.enabled
        return None


    def rowCount(self, parent):
        if not parent.isValid():
            return len(self.root.children)
        node = parent.internalPointer()
        if isinstance(node, PlayRegistry.Node):
            return 0
        else:
            return len(node.children)


    def parent(self, index):
        if not index.isValid():
            return QModelIndex()
        else:
            node = index.internalPointer()
            if node == None:
                return None
            elif node.parent == None:
                parentRow = 0
            else:
                parentRow = node.parent.row
            return self.createIndex(parentRow, 0, node.parent)    # FIXME: is this right?


    def index(self, row, column, parent):
        if not parent.isValid():
            return self.createIndex(row, column, self.root.children[row])
        parentNode = parent.internalPointer()
        return self.createIndex(row, column, parentNode.children[row])


    def headerData(self, section, orientation, role):
        if orientation == QtCore.Qt.Horizontal and role == QtCore.Qt.DisplayRole and section == 0:
            return 'Play'
        return None


    # this is implemented so we can enable/disable plays from the gui
    def setData(self, index, value, role):
        if role == QtCore.Qt.CheckStateRole:
            if index.isValid():
                playNode = index.internalPointer()
                if not isinstance(playNode, PlayRegistry.Node):
                    raise AssertionError("Only Play Nodes should be checkable...")
                playNode.enabled = not playNode.enabled
                self.dataChanged.emit(index, index)
                return True
        return False